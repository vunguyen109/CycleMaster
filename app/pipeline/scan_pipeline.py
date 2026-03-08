import logging
from datetime import date
import pandas as pd
import json
from sqlalchemy import text
from app.models import models
from app.models.db import SessionLocal
from app.services import data_service, feature_service, regime_service, scoring_service
from app.services import sector_service
from app.services import liquidity_service, validation_service
from app.services import llm_prep_service, llm_inference
from app.utils.config import settings


logger = logging.getLogger(__name__)


def run_daily_scan():
    session = SessionLocal()
    try:
        logger.info('Scan started')
        lookback = max(getattr(settings, 'lookback_min', 150), 150)
        logger.info(f'Config: data_provider={settings.data_provider} lookback_min={lookback} db={settings.database_url}')
        logger.info('Stage 0: Universe Load')
        symbols = data_service.get_symbols(session)
        if not symbols:
            logger.warning('No symbols in universe. Scan aborted.')
            return {
                'date': date.today(),
                'total_scanned': 0,
                'top_symbols': [],
                'market_regime': 'ACCUMULATION'
            }
        all_df = data_service.fetch_ohlcv(session, symbols)
        logger.info(f'Fetched OHLCV rows: {len(all_df)} for {len(symbols)} symbols')
        if not all_df.empty:
            by_sym = all_df.groupby('symbol')
            for sym, g in by_sym:
                logger.info(f'OHLCV {sym}: rows={len(g)} range={g["date"].min().date()}..{g["date"].max().date()}')
        vnindex_df = data_service.fetch_vnindex(session)
        logger.info(f'Fetched VNINDEX rows: {len(vnindex_df)}')
        if not vnindex_df.empty:
            logger.info(f'VNINDEX range={vnindex_df["date"].min().date()}..{vnindex_df["date"].max().date()}')
        else:
            logger.warning('VNINDEX empty after fetch')

        # Stage 1: Data Validation
        validated = {}
        invalid = {}
        min_sessions = 120
        missing_sector = []
        for symbol in symbols:
            df = all_df[all_df['symbol'] == symbol].copy()
            if df.empty:
                invalid[symbol] = 'no_data'
                continue
            df = df.sort_values('date')
            ok, reason = validation_service.validate_ohlcv(df, min_sessions=min_sessions)
            if not ok:
                invalid[symbol] = reason
                continue
            sector = session.query(models.Stock.sector).filter_by(symbol=symbol).scalar()
            if not sector:
                missing_sector.append(symbol)
            validated[symbol] = df
        if invalid:
            logger.warning(f'Validation skipped {len(invalid)} symbols: {", ".join(sorted(invalid.keys()))}')
        if missing_sector:
            logger.warning(f'Missing sector noted {len(missing_sector)} symbols: {", ".join(sorted(missing_sector))}')

        # Stage 2: Liquidity Computation
        liquidity_by_symbol = {}
        for symbol, df in validated.items():
            liquidity_by_symbol[symbol] = liquidity_service.compute_liquidity_metrics(df)
        liquidity_service.rank_liquidity(liquidity_by_symbol)

        # Stage 3: Liquidity Filtering
        scan_symbols = list(validated.keys())
        if not scan_symbols:
            logger.warning('No symbols to scan after validation')
        low_liquidity_count = 0
        for symbol, metrics in liquidity_by_symbol.items():
            if metrics.get('avg_value_20') is not None and metrics.get('avg_value_20') < settings.liquidity_min_avg_value:
                low_liquidity_count += 1
                logger.info(f'Liquidity below scan threshold but will still be scored: {symbol}')
        logger.info(f'Liquidity filter count (avg_value_20 < {settings.liquidity_min_avg_value:.0f}): {low_liquidity_count}')
        tradable_symbols = scan_symbols

        # Stage 4: Feature Engineering
        breadth20_hits = 0
        breadth50_hits = 0
        breadth_total = 0
        feature_cache = {}
        insufficient = []
        for symbol in tradable_symbols:
            df = validated[symbol]
            if len(df) < lookback:
                logger.warning(f'Insufficient OHLCV for {symbol}: {len(df)} rows, need >= {lookback}')
            df = feature_service.calculate_features(df, lookback=lookback)
            percentile = liquidity_by_symbol.get(symbol, {}).get('liquidity_percentile_rank')
            if percentile is not None:
                df.at[df.index[-1], 'liquidity_percentile_rank'] = percentile
            feature_service.save_features(session, symbol, df)
            last = df.iloc[-1]
            if not pd.isna(last['ma20']) and not pd.isna(last['ma50']):
                breadth_total += 1
                if last['close'] > last['ma20']:
                    breadth20_hits += 1
                if last['close'] > last['ma50']:
                    breadth50_hits += 1
            feature_cache[symbol] = df
        if insufficient:
            logger.warning(f'Insufficient lookback symbols: {", ".join(sorted(insufficient))}')

        # Stage 5: Market Regime Detection
        market_regime, confidence, regime_date = regime_service.detect_market_regime(session, vnindex_df)
        logger.info(f'Market regime: {market_regime} ({confidence:.1f}%) on {regime_date}')

        breadth20_pct = (breadth20_hits / breadth_total * 100) if breadth_total > 0 else 100.0
        breadth50_pct = (breadth50_hits / breadth_total * 100) if breadth_total > 0 else 100.0
        logger.info(f'Market breadth > MA20: {breadth20_pct:.1f}% | > MA50: {breadth50_pct:.1f}%')

        # Stage 6: Sector Strength Detection
        sector_map = {s.symbol: s.sector for s in session.query(models.Stock).all()}
        sector_metrics = sector_service.compute_sector_strength(feature_cache, sector_map, vnindex_df)
        for symbol, df in feature_cache.items():
            metrics = sector_service.get_symbol_sector_context(symbol, sector_map, sector_metrics)
            df.at[df.index[-1], 'sector_return_20d'] = metrics['sector_return_20d']
            df.at[df.index[-1], 'sector_rs_vs_index'] = metrics['sector_relative_strength']
            df.at[df.index[-1], 'sector_volume_momentum'] = metrics['sector_volume_change']
            df.at[df.index[-1], 'sector_breadth_pct'] = metrics['sector_breadth_pct']
            df.at[df.index[-1], 'sector_score'] = metrics['sector_score']
            feature_service.save_features(session, symbol, df)

        # Stage 7: Stock Phase Detection
        phase_cache = {}
        latest_scan_date = None
        for symbol, df in feature_cache.items():
            if latest_scan_date is None and not df.empty:
                latest_scan_date = df['date'].iloc[-1].date()
            prev_phase = None
            if latest_scan_date is not None:
                prev_phase_row = (
                    session.query(models.StockScore.regime)
                    .join(models.Stock, models.Stock.id == models.StockScore.stock_id)
                    .filter(models.Stock.symbol == symbol, models.StockScore.date < latest_scan_date)
                    .order_by(models.StockScore.date.desc())
                    .first()
                )
                prev_phase = prev_phase_row[0] if prev_phase_row else None
            phase_cache[symbol] = scoring_service.detect_stock_phase(
                df,
                vnindex_df,
                breadth20_pct=breadth20_pct,
                breadth50_pct=breadth50_pct,
                prev_phase=prev_phase
            )
            df.at[df.index[-1], 'rs_score'] = scoring_service.rs_score_0_10(df, vnindex_df)
            feature_service.save_features(session, symbol, df)

        # Stage 8-12: Scoring, Signal, Trade plan, Result validation, Save
        regime_counts = {}
        signal_counts = {'BUY': 0, 'SETUP': 0, 'WATCH': 0, 'AVOID': 0}
        score_values = []
        for symbol, df in feature_cache.items():
            score = scoring_service.score_stock(
                session,
                symbol,
                df,
                vnindex_df,
                market_regime,
                market_confidence=confidence,
                breadth20_pct=breadth20_pct,
                breadth50_pct=breadth50_pct,
                phase_context=phase_cache.get(symbol),
                sector_context=sector_service.get_symbol_sector_context(symbol, sector_map, sector_metrics)
            )
            ok, reason = scoring_service.validate_signal_output(score)
            if not ok:
                logger.warning(f'Signal validation failed for {symbol}: {reason}')
                continue
            scoring_service.save_score(session, symbol, df['date'].iloc[-1].date(), score)
            logger.info(f'Scored {symbol}: regime={score["regime"]} score={score["score"]:.1f} action={score.get("action")}')
            regime_counts[score['regime']] = regime_counts.get(score['regime'], 0) + 1
            sig = score.get('trade_signal') or score.get('action') or 'AVOID'
            if sig not in signal_counts:
                signal_counts[sig] = 0
            signal_counts[sig] += 1
            score_values.append(score['score'])

        if regime_counts:
            logger.info(f'Regime distribution: {regime_counts}')
            total_regime = sum(regime_counts.values())
            top_regime = max(regime_counts.values()) if total_regime > 0 else 0
            if total_regime > 0 and top_regime / total_regime > 0.7:
                dominant = max(regime_counts, key=regime_counts.get)
                logger.warning(f'Regime imbalance: {dominant} at {top_regime}/{total_regime}')
            if len(regime_counts.keys()) < 3:
                logger.warning(f'Regime category count low: {len(regime_counts.keys())}')
        if score_values:
            avg_score = sum(score_values) / max(len(score_values), 1)
            logger.info(f'Average score: {avg_score:.2f}')
            hist, bins = pd.cut(pd.Series(score_values), bins=[0, 20, 40, 60, 80, 100], include_lowest=True).value_counts(sort=False), [0, 20, 40, 60, 80, 100]
            logger.info(f'Score histogram bins {bins}: {[int(v) for v in hist.values]}')
        logger.info(
            f'Signal distribution: BUY={signal_counts.get("BUY",0)} '
            f'SETUP={signal_counts.get("SETUP",0)} WATCH={signal_counts.get("WATCH",0)} '
            f'AVOID={signal_counts.get("AVOID",0)}'
        )



        top_scores = session.execute(
            text(
                """
                SELECT s.symbol, sc.score, sc.regime
                FROM stock_scores sc
                JOIN stocks s ON s.id = sc.stock_id
                WHERE sc.date = (SELECT MAX(date) FROM stock_scores)
                ORDER BY sc.score DESC
                LIMIT 5
                """
            )
        ).fetchall()
        top_symbols = [row[0] for row in top_scores]

        summary = {
            'date': regime_date,
            'total_scanned': len(symbols),
            'top_symbols': top_symbols,
            'market_regime': market_regime
        }

        return summary
    finally:
        session.close()
