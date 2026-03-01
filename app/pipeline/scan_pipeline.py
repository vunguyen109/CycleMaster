import logging
from datetime import date
import pandas as pd
from sqlalchemy import text
from app.models import models
from app.models.db import SessionLocal
from app.services import data_service, feature_service, regime_service, scoring_service
from app.services import liquidity_service, validation_service
from app.utils.config import settings


logger = logging.getLogger(__name__)


def run_daily_scan():
    session = SessionLocal()
    try:
        logger.info('Scan started')
        lookback = max(getattr(settings, 'lookback_min', 150), 150)
        logger.info(f'Config: data_provider={settings.data_provider} lookback_min={lookback} db={settings.database_url}')
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

        # Step 0: Data validation
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

        # Step 1: Liquidity computation & ranking
        liquidity_by_symbol = {}
        for symbol, df in validated.items():
            liquidity_by_symbol[symbol] = liquidity_service.compute_liquidity_metrics(df)
        liquidity_service.rank_liquidity(liquidity_by_symbol)

        # Step 2: Liquidity filtering is disabled for trading signals.
        # we still compute liquidity metrics for informational purposes but every
        # validated symbol will be evaluated regardless of value/volume.
        scan_symbols = list(validated.keys())
        if not scan_symbols:
            logger.warning('No symbols to scan after validation')
        # log any that fail the traditional thresholds but do not exclude them
        for symbol, metrics in liquidity_by_symbol.items():
            if metrics.get('avg_value_20') is not None and metrics.get('avg_value_20') < settings.liquidity_min_scan_value:
                logger.info(f'Liquidity below scan threshold but will still be scored: {symbol}')
        tradable_symbols = scan_symbols

        # Step 3: Feature calculation
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

        # Step 4: Market regime detection
        market_regime, confidence, regime_date = regime_service.detect_market_regime(session, vnindex_df)
        logger.info(f'Market regime: {market_regime} ({confidence:.1f}%) on {regime_date}')

        breadth20_pct = (breadth20_hits / breadth_total * 100) if breadth_total > 0 else 100.0
        breadth50_pct = (breadth50_hits / breadth_total * 100) if breadth_total > 0 else 100.0
        logger.info(f'Market breadth > MA20: {breadth20_pct:.1f}% | > MA50: {breadth50_pct:.1f}%')

        # Step 5: Stock phase detection
        phase_cache = {}
        for symbol, df in feature_cache.items():
            phase_cache[symbol] = scoring_service.detect_stock_phase(
                df,
                vnindex_df,
                breadth20_pct=breadth20_pct,
                breadth50_pct=breadth50_pct
            )
            df.at[df.index[-1], 'rs_score'] = scoring_service.rs_score_0_10(df, vnindex_df)
            feature_service.save_features(session, symbol, df)

        # Sector momentum
        sector_map = {s.symbol: s.sector for s in session.query(models.Stock).all()}
        sector_bucket = {}
        for symbol, df in feature_cache.items():
            sector = sector_map.get(symbol) or 'UNKNOWN'
            ret20 = df['close'].pct_change(20).iloc[-1]
            vol_ma5 = df['volume'].rolling(5).mean().iloc[-1]
            vol_ma20 = df['volume'].rolling(20).mean().iloc[-1]
            vol_mom = (vol_ma5 / vol_ma20 - 1.0) if pd.notna(vol_ma5) and pd.notna(vol_ma20) and vol_ma20 > 0 else 0.0
            breadth_hit = 1 if pd.notna(df['ma20'].iloc[-1]) and df['close'].iloc[-1] > df['ma20'].iloc[-1] else 0
            bucket = sector_bucket.setdefault(sector, {'ret20': [], 'vol_mom': [], 'breadth': []})
            if pd.notna(ret20):
                bucket['ret20'].append(ret20)
            if pd.notna(vol_mom):
                bucket['vol_mom'].append(vol_mom)
            bucket['breadth'].append(breadth_hit)

        sector_metrics = {}
        vni_ret20 = vnindex_df['close'].pct_change(20).iloc[-1]
        for sector, bucket in sector_bucket.items():
            ret20_avg = float(sum(bucket['ret20']) / max(len(bucket['ret20']), 1)) if bucket['ret20'] else 0.0
            vol_mom_avg = float(sum(bucket['vol_mom']) / max(len(bucket['vol_mom']), 1)) if bucket['vol_mom'] else 0.0
            breadth_pct = float(sum(bucket['breadth']) / max(len(bucket['breadth']), 1) * 100)
            rs_vs_index = float(ret20_avg - vni_ret20) if pd.notna(vni_ret20) else ret20_avg
            sector_metrics[sector] = {
                'sector_return_20d': ret20_avg,
                'sector_rs_vs_index': rs_vs_index,
                'sector_volume_momentum': vol_mom_avg,
                'sector_breadth_pct': breadth_pct
            }

        for symbol, df in feature_cache.items():
            sector = sector_map.get(symbol) or 'UNKNOWN'
            metrics = sector_metrics.get(sector, {
                'sector_return_20d': 0.0,
                'sector_rs_vs_index': 0.0,
                'sector_volume_momentum': 0.0,
                'sector_breadth_pct': 0.0
            })
            df.at[df.index[-1], 'sector_return_20d'] = metrics['sector_return_20d']
            df.at[df.index[-1], 'sector_rs_vs_index'] = metrics['sector_rs_vs_index']
            df.at[df.index[-1], 'sector_volume_momentum'] = metrics['sector_volume_momentum']
            df.at[df.index[-1], 'sector_breadth_pct'] = metrics['sector_breadth_pct']
            feature_service.save_features(session, symbol, df)

        # Step 6-8: Scoring, signal validation, save
        regime_counts = {}
        action_counts = {'BUY': 0, 'WATCH': 0, 'AVOID': 0}
        score_values = []
        for symbol, df in feature_cache.items():
            score = scoring_service.score_stock(
                session,
                symbol,
                df,
                vnindex_df,
                market_regime,
                breadth20_pct=breadth20_pct,
                breadth50_pct=breadth50_pct,
                phase_context=phase_cache.get(symbol),
                sector_context=sector_metrics.get(sector_map.get(symbol) or 'UNKNOWN')
            )
            ok, reason = scoring_service.validate_signal_output(score)
            if not ok:
                logger.warning(f'Signal validation failed for {symbol}: {reason}')
                continue
            scoring_service.save_score(session, symbol, df['date'].iloc[-1].date(), score)
            logger.info(f'Scored {symbol}: regime={score["regime"]} score={score["score"]:.1f} action={score.get("action")}')
            regime_counts[score['regime']] = regime_counts.get(score['regime'], 0) + 1
            action_counts[score.get('action', 'AVOID')] = action_counts.get(score.get('action', 'AVOID'), 0) + 1
            score_values.append(score['score'])
            # legacy QC checks removed; entry/stop/target are always produced so no need
            # check buy_zone or risk_reward negativity anymore

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
        logger.info(f'Action distribution: BUY={action_counts.get("BUY",0)} WATCH={action_counts.get("WATCH",0)} AVOID={action_counts.get("AVOID",0)}')



        top_scores = session.execute(
            text(
                """
                SELECT s.symbol, sc.score, sc.regime
                FROM stock_scores sc
                JOIN stocks s ON s.id = sc.stock_id
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
