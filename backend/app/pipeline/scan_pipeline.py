import logging
from datetime import date
import pandas as pd
from sqlalchemy import text
from app.models.db import SessionLocal
from app.services import data_service, feature_service, regime_service, scoring_service


logger = logging.getLogger(__name__)


def run_daily_scan():
    session = SessionLocal()
    try:
        logger.info('Scan started')
        symbols = data_service.get_symbols(session)
        if not symbols:
            logger.warning('No symbols in watchlist. Scan aborted.')
            return {
                'date': date.today(),
                'total_scanned': 0,
                'top_symbols': [],
                'market_regime': 'ACCUMULATION'
            }
        all_df = data_service.fetch_ohlcv(session, symbols)
        logger.info(f'Fetched OHLCV rows: {len(all_df)} for {len(symbols)} symbols')
        vnindex_df = data_service.fetch_vnindex(session)
        logger.info(f'Fetched VNINDEX rows: {len(vnindex_df)}')

        market_regime, confidence, regime_date = regime_service.detect_market_regime(session, vnindex_df)
        logger.info(f'Market regime: {market_regime} ({confidence:.1f}%) on {regime_date}')

        breadth20_hits = 0
        breadth50_hits = 0
        breadth_total = 0
        feature_cache = {}
        for symbol in symbols:
            df = all_df[all_df['symbol'] == symbol].copy()
            if df.empty:
                logger.warning(f'No OHLCV data for {symbol}')
                continue
            df = feature_service.calculate_features(df)
            feature_service.save_features(session, symbol, df)
            last = df.iloc[-1]
            if not pd.isna(last['ma20']) and not pd.isna(last['ma50']):
                breadth_total += 1
                if last['close'] > last['ma20']:
                    breadth20_hits += 1
                if last['close'] > last['ma50']:
                    breadth50_hits += 1
            feature_cache[symbol] = df

        breadth20_pct = (breadth20_hits / breadth_total * 100) if breadth_total > 0 else 100.0
        breadth50_pct = (breadth50_hits / breadth_total * 100) if breadth_total > 0 else 100.0
        logger.info(f'Market breadth > MA20: {breadth20_pct:.1f}% | > MA50: {breadth50_pct:.1f}%')

        for symbol, df in feature_cache.items():
            score = scoring_service.score_stock(
                session,
                symbol,
                df,
                vnindex_df,
                market_regime,
                breadth20_pct=breadth20_pct,
                breadth50_pct=breadth50_pct
            )
            scoring_service.save_score(session, symbol, df['date'].iloc[-1].date(), score)
            logger.info(f'Scored {symbol}: regime={score["regime"]} score={score["score"]:.1f}')

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
