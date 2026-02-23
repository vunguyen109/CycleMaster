from fastapi import APIRouter, HTTPException
from sqlalchemy import text, bindparam
import numpy as np
from app.models.db import SessionLocal
from app.models import models
from app.models.schemas import MarketRegimeOut, StockTopOut, StockDetailOut, ScanLatestOut, AlertOut, PortfolioItemOut, BacktestOut, MarketSeriesOut, MarketSeriesPoint, PortfolioUpsertIn
from app.pipeline.scan_pipeline import run_daily_scan
from app.services.alert_service import get_distribution_alerts
from app.services.portfolio_service import get_portfolio
from app.services import data_service
from app.backtest_engine import run_backtest
from app.utils.config import settings


router = APIRouter()


def get_session():
    return SessionLocal()


def ensure_latest_data():
    session = get_session()
    try:
        has_regime = session.query(models.MarketRegime).first() is not None
        has_scores = session.query(models.StockScore).first() is not None
        if not has_regime or not has_scores:
            run_daily_scan()
    finally:
        session.close()


@router.get('/market/regime', response_model=MarketRegimeOut)
def market_regime():
    ensure_latest_data()
    session = get_session()
    try:
        rows = session.query(models.MarketRegime).order_by(models.MarketRegime.date.desc()).limit(2).all()
        row = rows[0] if rows else None
        if not row:
            raise HTTPException(status_code=404, detail='No market regime data')
        prev = rows[1] if len(rows) > 1 else None
        return MarketRegimeOut(
            regime=row.regime,
            confidence=row.confidence,
            date=row.date,
            prev_regime=prev.regime if prev else None,
            prev_confidence=prev.confidence if prev else None,
            confidence_change=(row.confidence - prev.confidence) if prev else None
        )
    finally:
        session.close()


@router.get('/stocks/top', response_model=list[StockTopOut])
def top_stocks():
    ensure_latest_data()
    session = get_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT s.symbol, s.sector, sc.score, sc.regime, sc.buy_zone, sc.tp_zone, sc.stop_loss,
                       sc.risk_reward, sc.setup_status, sc.market_alignment, sc.setup_tier
                FROM stock_scores sc
                JOIN stocks s ON s.id = sc.stock_id
                WHERE sc.date = (SELECT MAX(date) FROM stock_scores)
                  AND sc.setup_status != 'LOW_LIQUIDITY'
                  AND sc.regime IN ('ACCUMULATION_STRONG', 'ACCUMULATION_WEAK', 'ACCUMULATION', 'MARKUP')
                ORDER BY sc.score DESC
                """
            )
        ).fetchall()

        if not rows:
            return []

        scores = [r[2] for r in rows if r[2] is not None]
        if not scores:
            return []
        threshold = float(np.quantile(scores, settings.top_percentile))

        candidates = [r for r in rows if r[2] is not None and r[2] >= threshold]
        candidates.sort(key=lambda r: r[2], reverse=True)

        sector_counts = {}
        results = []
        window = max(settings.top_sector_window, settings.top_n)
        for r in candidates:
            symbol, sector, score, regime, buy_zone, tp_zone, stop_loss, rr, setup_status, market_alignment, setup_tier = r
            sector_key = sector or 'UNKNOWN'
            if len(results) < window:
                if sector_counts.get(sector_key, 0) >= settings.top_sector_cap:
                    continue
            feature = session.query(models.StockFeatures).filter_by(
                stock_id=session.query(models.Stock.id).filter_by(symbol=symbol).scalar()
            ).order_by(models.StockFeatures.date.desc()).first()
            ohlcv = session.query(models.OHLCV).filter_by(symbol=symbol).order_by(models.OHLCV.date.desc()).first()
            last_close = float(ohlcv.close) if ohlcv else None
            results.append(StockTopOut(
                symbol=symbol,
                regime=regime,
                score=float(score),
                last_close=last_close,
                buy_zone=buy_zone,
                take_profit=tp_zone,
                stop_loss=stop_loss,
                risk_reward=float(rr) if rr is not None else None,
                liquidity_score=float(feature.liquidity_score) if feature and feature.liquidity_score is not None else None,
                setup_status=setup_status,
                market_alignment=market_alignment,
                setup_tier=setup_tier
            ))
            sector_counts[sector_key] = sector_counts.get(sector_key, 0) + 1
            if len(results) >= settings.top_n:
                break

        return results
    finally:
        session.close()




@router.get('/stocks/{symbol}', response_model=StockDetailOut)
def stock_detail(symbol: str):
    ensure_latest_data()
    session = get_session()
    try:
        stock = session.query(models.Stock).filter_by(symbol=symbol).first()
        if not stock:
            raise HTTPException(status_code=404, detail='Symbol not found')
        feature = session.query(models.StockFeatures).filter_by(stock_id=stock.id).order_by(models.StockFeatures.date.desc()).first()
        score = session.query(models.StockScore).filter_by(stock_id=stock.id).order_by(models.StockScore.date.desc()).first()
        if not feature or not score:
            raise HTTPException(status_code=404, detail='No data for symbol')
        return StockDetailOut(
            symbol=symbol,
            features={
                'rsi': feature.rsi,
                'macd': feature.macd,
                'adx': feature.adx,
                'volume_ratio': feature.volume_ratio,
                'atr': feature.atr,
                'ma20': feature.ma20,
                'ma50': feature.ma50,
                'ma100': feature.ma100,
                'avg_volume_20': feature.avg_volume_20,
                'avg_value_20': feature.avg_value_20,
                'liquidity_score': feature.liquidity_score,
                'liquidity_percentile_rank': feature.liquidity_percentile_rank,
                'rs_score': feature.rs_score,
                'sector_return_20d': feature.sector_return_20d,
                'sector_rs_vs_index': feature.sector_rs_vs_index,
                'sector_volume_momentum': feature.sector_volume_momentum,
                'sector_breadth_pct': feature.sector_breadth_pct
            },
            regime=score.regime,
            score=score.score,
            suggested_trade={
                'buy_zone': score.buy_zone,
                'take_profit': score.tp_zone,
                'stop_loss': score.stop_loss,
                'risk_reward': score.risk_reward,
                'confidence': score.confidence,
                'setup_status': score.setup_status,
                'market_alignment': score.market_alignment,
                'setup_tier': score.setup_tier
            }
        )
    finally:
        session.close()


@router.get('/scan/latest', response_model=ScanLatestOut)
def scan_latest():
    summary = run_daily_scan()
    return ScanLatestOut(**summary)


@router.get('/alerts/distribution', response_model=list[AlertOut])
def alerts_distribution():
    session = get_session()
    try:
        alerts = get_distribution_alerts(session)
        result = []
        for score in alerts:
            stock = session.query(models.Stock).filter_by(id=score.stock_id).first()
            result.append(AlertOut(symbol=stock.symbol, regime=score.regime, confidence=score.confidence, reason='Distribution pattern'))
        return result
    finally:
        session.close()


@router.get('/portfolio', response_model=list[PortfolioItemOut])
def portfolio():
    session = get_session()
    try:
        items = get_portfolio(session)
        output = []
        for item in items:
            stock = session.query(models.Stock).filter_by(symbol=item.symbol).first()
            latest_score = None
            latest_regime = None
            warning = None
            last_close = None
            pnl_vnd = None
            buy_zone = None
            take_profit = None
            if stock:
                score = session.query(models.StockScore).filter_by(stock_id=stock.id).order_by(models.StockScore.date.desc()).first()
                if score:
                    latest_score = score.score
                    latest_regime = score.regime
                    buy_zone = score.buy_zone
                    take_profit = score.tp_zone
                    if score.regime == 'MARKDOWN':
                        warning = 'Holding moved to MARKDOWN'
                ohlcv = session.query(models.OHLCV).filter_by(symbol=item.symbol).order_by(models.OHLCV.date.desc()).first()
                if ohlcv:
                    last_close = float(ohlcv.close)
                    pnl_vnd = (last_close - float(item.avg_price)) * float(item.quantity)
            output.append(PortfolioItemOut(
                symbol=item.symbol,
                quantity=item.quantity,
                avg_price=item.avg_price,
                latest_regime=latest_regime,
                latest_score=latest_score,
                warning=warning,
                last_close=last_close,
                pnl_vnd=pnl_vnd,
                buy_zone=buy_zone,
                take_profit=take_profit
            ))
        return output
    finally:
        session.close()


@router.post('/portfolio', response_model=PortfolioItemOut)
def add_portfolio(payload: PortfolioUpsertIn):
    session = get_session()
    try:
        symbol = payload.symbol.strip().upper()
        item = session.query(models.Portfolio).filter_by(symbol=symbol).first()
        if item:
            item.quantity = payload.quantity
            item.avg_price = payload.avg_price
        else:
            item = models.Portfolio(symbol=symbol, quantity=payload.quantity, avg_price=payload.avg_price)
            session.add(item)
        session.commit()

        stock = session.query(models.Stock).filter_by(symbol=symbol).first()
        latest_score = None
        latest_regime = None
        warning = None
        last_close = None
        pnl_vnd = None
        buy_zone = None
        take_profit = None
        if stock:
            score = session.query(models.StockScore).filter_by(stock_id=stock.id).order_by(models.StockScore.date.desc()).first()
            if score:
                latest_score = score.score
                latest_regime = score.regime
                buy_zone = score.buy_zone
                take_profit = score.tp_zone
                if score.regime == 'MARKDOWN':
                    warning = 'Holding moved to MARKDOWN'
            ohlcv = session.query(models.OHLCV).filter_by(symbol=symbol).order_by(models.OHLCV.date.desc()).first()
            if ohlcv:
                last_close = float(ohlcv.close)
                pnl_vnd = (last_close - float(item.avg_price)) * float(item.quantity)

        return PortfolioItemOut(
            symbol=item.symbol,
            quantity=item.quantity,
            avg_price=item.avg_price,
            latest_regime=latest_regime,
            latest_score=latest_score,
            warning=warning,
            last_close=last_close,
            pnl_vnd=pnl_vnd,
            buy_zone=buy_zone,
            take_profit=take_profit
        )
    finally:
        session.close()


@router.put('/portfolio/{symbol}', response_model=PortfolioItemOut)
def update_portfolio(symbol: str, payload: PortfolioUpsertIn):
    session = get_session()
    try:
        item = session.query(models.Portfolio).filter_by(symbol=symbol.upper()).first()
        if not item:
            raise HTTPException(status_code=404, detail='Symbol not found in portfolio')
        item.quantity = payload.quantity
        item.avg_price = payload.avg_price
        session.commit()

        stock = session.query(models.Stock).filter_by(symbol=item.symbol).first()
        latest_score = None
        latest_regime = None
        warning = None
        last_close = None
        pnl_vnd = None
        buy_zone = None
        take_profit = None
        if stock:
            score = session.query(models.StockScore).filter_by(stock_id=stock.id).order_by(models.StockScore.date.desc()).first()
            if score:
                latest_score = score.score
                latest_regime = score.regime
                buy_zone = score.buy_zone
                take_profit = score.tp_zone
                if score.regime == 'MARKDOWN':
                    warning = 'Holding moved to MARKDOWN'
            ohlcv = session.query(models.OHLCV).filter_by(symbol=item.symbol).order_by(models.OHLCV.date.desc()).first()
            if ohlcv:
                last_close = float(ohlcv.close)
                pnl_vnd = (last_close - float(item.avg_price)) * float(item.quantity)

        return PortfolioItemOut(
            symbol=item.symbol,
            quantity=item.quantity,
            avg_price=item.avg_price,
            latest_regime=latest_regime,
            latest_score=latest_score,
            warning=warning,
            last_close=last_close,
            pnl_vnd=pnl_vnd,
            buy_zone=buy_zone,
            take_profit=take_profit
        )
    finally:
        session.close()


@router.delete('/portfolio/{symbol}')
def delete_portfolio(symbol: str):
    session = get_session()
    try:
        item = session.query(models.Portfolio).filter_by(symbol=symbol.upper()).first()
        if not item:
            raise HTTPException(status_code=404, detail='Symbol not found in portfolio')
        session.delete(item)
        session.commit()
        return {'status': 'deleted', 'symbol': symbol.upper()}
    finally:
        session.close()


@router.get('/backtest/{symbol}', response_model=BacktestOut)
def backtest(symbol: str, strategy: str = 'breakout20'):
    session = get_session()
    try:
        result = run_backtest(session, symbol, strategy)
        if not result:
            raise HTTPException(status_code=404, detail='Backtest not available')
        return BacktestOut(**result)
    finally:
        session.close()


@router.get('/market/vnindex/series', response_model=MarketSeriesOut)
def vnindex_series(limit: int = 120):
    session = get_session()
    try:
        rows = session.query(models.OHLCV).filter_by(symbol='VNINDEX').order_by(models.OHLCV.date.desc()).limit(limit).all()
        if not rows:
            data_service.fetch_vnindex(session)
            rows = session.query(models.OHLCV).filter_by(symbol='VNINDEX').order_by(models.OHLCV.date.desc()).limit(limit).all()
        series = list(reversed(rows))
        return MarketSeriesOut(
            symbol='VNINDEX',
            series=[MarketSeriesPoint(date=r.date, close=float(r.close)) for r in series]
        )
    finally:
        session.close()
