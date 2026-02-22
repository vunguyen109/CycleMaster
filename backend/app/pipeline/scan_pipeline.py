import logging
from app.models.db import SessionLocal
from app.services import data_service, feature_service, regime_service, scoring_service


logger = logging.getLogger(__name__)


def run_daily_scan():
    session = SessionLocal()
    try:
        symbols = data_service.get_symbols(session)
        all_df = data_service.fetch_ohlcv(session, symbols)
        vnindex_df = data_service.fetch_vnindex(session)

        market_regime, confidence, regime_date = regime_service.detect_market_regime(session, vnindex_df)

        for symbol in symbols:
            df = all_df[all_df['symbol'] == symbol].copy()
            if df.empty:
                continue
            df = feature_service.calculate_features(df)
            feature_service.save_features(session, symbol, df)
            score = scoring_service.score_stock(session, symbol, df, vnindex_df, market_regime)
            scoring_service.save_score(session, symbol, df['date'].iloc[-1].date(), score)

        top_scores = session.execute(
            """
            SELECT s.symbol, sc.score, sc.regime
            FROM stock_scores sc
            JOIN stocks s ON s.id = sc.stock_id
            ORDER BY sc.score DESC
            LIMIT 5
            """
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
