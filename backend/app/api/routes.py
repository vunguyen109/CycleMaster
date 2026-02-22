from fastapi import APIRouter, HTTPException
from app.models.db import SessionLocal
from app.models import models
from app.models.schemas import MarketRegimeOut, StockTopOut, StockDetailOut, ScanLatestOut, AlertOut, PortfolioItemOut, BacktestOut
from app.pipeline.scan_pipeline import run_daily_scan
from app.services.alert_service import get_distribution_alerts
from app.services.portfolio_service import get_portfolio
from app.backtest_engine import run_backtest


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
        row = session.query(models.MarketRegime).order_by(models.MarketRegime.date.desc()).first()
        if not row:
            raise HTTPException(status_code=404, detail='No market regime data')
        return MarketRegimeOut(regime=row.regime, confidence=row.confidence, date=row.date)
    finally:
        session.close()


@router.get('/stocks/top', response_model=list[StockTopOut])
def top_stocks():
    ensure_latest_data()
    session = get_session()
    try:
        rows = session.execute(
            """
            SELECT s.symbol, sc.regime, sc.score, sc.buy_zone, sc.tp_zone, sc.risk_reward
            FROM stock_scores sc
            JOIN stocks s ON s.id = sc.stock_id
            ORDER BY sc.score DESC
            LIMIT 5
            """
        ).fetchall()
        return [StockTopOut(
            symbol=r[0],
            regime=r[1],
            score=float(r[2]),
            buy_zone=r[3],
            take_profit=r[4],
            risk_reward=float(r[5])
        ) for r in rows]
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
                'ma100': feature.ma100
            },
            regime=score.regime,
            score=score.score,
            suggested_trade={
                'buy_zone': score.buy_zone,
                'take_profit': score.tp_zone,
                'stop_loss': score.stop_loss,
                'risk_reward': score.risk_reward,
                'confidence': score.confidence
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
            if stock:
                score = session.query(models.StockScore).filter_by(stock_id=stock.id).order_by(models.StockScore.date.desc()).first()
                if score:
                    latest_score = score.score
                    latest_regime = score.regime
                    if score.regime == 'MARKDOWN':
                        warning = 'Holding moved to MARKDOWN'
            output.append(PortfolioItemOut(
                symbol=item.symbol,
                quantity=item.quantity,
                avg_price=item.avg_price,
                latest_regime=latest_regime,
                latest_score=latest_score,
                warning=warning
            ))
        return output
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
