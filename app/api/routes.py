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
PRICE_SCALE = 1000.0


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


def _compute_trade_params(session, symbol, last_close, feature=None):
    # Return trade plan with current engine defaults (stop=1.5*ATR, target=3*ATR).
    if last_close is None or last_close <= 0:
        return None, None, None, None
    # ATR fallback logic
    atr_val = None
    if feature and getattr(feature, 'atr', None) and feature.atr > 0:
        atr_val = float(feature.atr) * PRICE_SCALE
    elif feature and getattr(feature, 'ma20', None) and feature.ma20 > 0:
        atr_val = float(feature.ma20) * PRICE_SCALE
    else:
        # compute 20-day range from OHLCV
        highs = session.query(models.OHLCV.high).filter_by(symbol=symbol).order_by(models.OHLCV.date.desc()).limit(20).all()
        lows = session.query(models.OHLCV.low).filter_by(symbol=symbol).order_by(models.OHLCV.date.desc()).limit(20).all()
        if highs and lows:
            high_vals = [h[0] for h in highs if h[0] is not None]
            low_vals = [l[0] for l in lows if l[0] is not None]
            if high_vals and low_vals:
                high_val = max(high_vals)
                low_val = min(low_vals)
                range_val = (high_val - low_val) / 3.5 if high_val > low_val else high_val * 0.03
                atr_val = float(range_val) if range_val > 0 else 1.0
                atr_val *= PRICE_SCALE
    atr_val = max(atr_val or 0.0, 1e-6)
    entry = last_close
    if feature and getattr(feature, 'ma20', None) and feature.ma20 > 0:
        ma20_scaled = float(feature.ma20) * PRICE_SCALE
        if abs(last_close / ma20_scaled - 1.0) <= 0.01:
            entry = ma20_scaled
    stop = entry - 1.5 * atr_val
    target = entry + 3.0 * atr_val
    if stop <= 0:
        stop = entry * 0.01
    if target <= 0:
        target = entry * 1.01
    rr = (target - entry) / max(entry - stop, 1e-6)
    return entry, stop, target, rr

@router.get('/stocks/top', response_model=list[StockTopOut])
def top_stocks():
    ensure_latest_data()
    session = get_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT s.symbol, s.sector, sc.score, sc.regime, sc.buy_zone_low, sc.buy_zone_high, sc.tp_zone, sc.stop_loss,
                       sc.risk_reward, sc.setup_status, sc.market_alignment, sc.trade_signal, sc.sector_score, sc.setup_tier, sc.model_version
                FROM stock_scores sc
                JOIN stocks s ON s.id = sc.stock_id
                WHERE sc.date = (SELECT MAX(date) FROM stock_scores)
                """
            )
        ).fetchall()

        if not rows:
            return []

        # compute setup_quality for ranking (score * rr)
        qualities = []
        for r in rows:
            score_val = r[2]
            rr_val = r[8]
            if score_val is not None and rr_val is not None:
                try:
                    qualities.append(float(score_val) * float(rr_val))
                except Exception:
                    pass
        if not qualities:
            return []
        threshold = float(np.quantile(qualities, settings.top_percentile))

        # select candidates meeting quality threshold
        candidates = []
        for r in rows:
            score_val = r[2]
            rr_val = r[8]
            qual = None
            if score_val is not None and rr_val is not None:
                try:
                    qual = float(score_val) * float(rr_val)
                except Exception:
                    qual = None
            if qual is not None and qual >= threshold:
                candidates.append((r, qual))
        # sort by descending quality
        candidates.sort(key=lambda x: x[1], reverse=True)
        # unwrap tuples
        candidates = [x[0] for x in candidates]

        sector_counts = {}
        results = []
        window = max(settings.top_sector_window, settings.top_n)
        for r in candidates:
            symbol, sector, score, regime, buy_zone_low, buy_zone_high, tp_zone, stop_loss, rr, setup_status, market_alignment, trade_signal, sector_score, setup_tier, model_version = r
            sector_key = sector or 'UNKNOWN'
            if len(results) < window:
                if sector_counts.get(sector_key, 0) >= settings.top_sector_cap:
                    continue
            feature = session.query(models.StockFeatures).filter_by(
                stock_id=session.query(models.Stock.id).filter_by(symbol=symbol).scalar()
            ).order_by(models.StockFeatures.date.desc()).first()
            ohlcv = session.query(models.OHLCV).filter_by(symbol=symbol).order_by(models.OHLCV.date.desc()).first()
            last_close = float(ohlcv.close) * PRICE_SCALE if ohlcv else None
            if setup_status in ('INVALID_PHASE', 'LOW_LIQUIDITY', 'DATA_ERROR', 'RR_REJECTED', 'NO_TRADE_PLAN'):
                entry_val, stop_val, target_val, rr_val = (last_close, None, None, None)
            else:
                entry_val, stop_val, target_val, rr_val = _compute_trade_params(session, symbol, last_close, feature)
            setup_quality_val = (float(score) * rr_val) if (rr_val is not None and score is not None) else None
            results.append(StockTopOut(
                symbol=symbol,
                regime=regime,
                score=float(score),
                last_close=last_close,
                buy_zone_low=float(buy_zone_low) if buy_zone_low is not None else None,
                buy_zone_high=float(buy_zone_high) if buy_zone_high is not None else None,
                take_profit=float(tp_zone) if tp_zone is not None else None,
                stop_loss=stop_val,
                risk_reward=rr_val,
                action=setup_status,
                entry=entry_val,
                stop=stop_val,
                target=target_val,
                rr=rr_val,
                setup_quality=setup_quality_val,
                liquidity_score=float(feature.liquidity_score) if feature and feature.liquidity_score is not None else None,
                setup_status=setup_status,
                market_alignment=market_alignment,
                trade_signal=trade_signal,
                sector_score=float(sector_score) if sector_score is not None else None,
                setup_tier=setup_tier,
                model_version=model_version
            ))
            sector_counts[sector_key] = sector_counts.get(sector_key, 0) + 1
            if len(results) >= settings.top_n:
                break

        return results
    finally:
        session.close()




@router.get('/analysis/latest', response_model=list[StockTopOut])
def analysis_latest():
    """Return the most recent scan/score entry for every stock symbol.
    This endpoint is primarily used by the frontend page that displays all
    analysis results, making it easier to review how the model is behaving.
    """
    ensure_latest_data()
    session = get_session()
    try:
        # grab the newest date available in the scores table
        rows = session.execute(
            text(
                """
                SELECT s.symbol,
                       sc.regime,
                       sc.score,
                       sc.buy_zone_low,
                       sc.buy_zone_high,
                       sc.tp_zone,
                       sc.stop_loss,
                       sc.risk_reward,
                       sc.setup_status,
                       sc.market_alignment,
                       sc.trade_signal,
                       sc.sector_score,
                       sc.setup_tier,
                       sc.model_version
                FROM stock_scores sc
                JOIN stocks s ON s.id = sc.stock_id
                WHERE sc.date = (SELECT MAX(date) FROM stock_scores)
                """
            )
        ).fetchall()

        results: list[StockTopOut] = []
        for r in rows:
            symbol, regime, score, buy_zone_low, buy_zone_high, tp_zone, stop_loss, rr, setup_status, market_alignment, trade_signal, sector_score, setup_tier, model_version = r
            # enrich with last close and liquidity score similar to top_stocks
            feature = session.query(models.StockFeatures).filter_by(
                stock_id=session.query(models.Stock.id).filter_by(symbol=symbol).scalar()
            ).order_by(models.StockFeatures.date.desc()).first()
            ohlcv = session.query(models.OHLCV).filter_by(symbol=symbol).order_by(models.OHLCV.date.desc()).first()
            last_close = float(ohlcv.close) * PRICE_SCALE if ohlcv else None
            if setup_status in ('INVALID_PHASE', 'LOW_LIQUIDITY', 'DATA_ERROR', 'RR_REJECTED', 'NO_TRADE_PLAN'):
                entry_val, stop_val, target_val, rr_val = (last_close, None, None, None)
            else:
                entry_val, stop_val, target_val, rr_val = _compute_trade_params(session, symbol, last_close, feature)
            setup_quality_val = (float(score) * rr_val) if (rr_val is not None and score is not None) else None
            results.append(StockTopOut(
                symbol=symbol,
                regime=regime,
                score=float(score) if score is not None else 0.0,
                last_close=last_close,
                buy_zone_low=float(buy_zone_low) if buy_zone_low is not None else None,
                buy_zone_high=float(buy_zone_high) if buy_zone_high is not None else None,
                take_profit=float(tp_zone) if tp_zone is not None else None,
                stop_loss=stop_val,
                risk_reward=rr_val,
                action=setup_status,
                entry=entry_val,
                stop=stop_val,
                target=target_val,
                rr=rr_val,
                setup_quality=setup_quality_val,
                liquidity_score=float(feature.liquidity_score) if feature and feature.liquidity_score is not None else None,
                setup_status=setup_status,
                market_alignment=market_alignment,
                trade_signal=trade_signal,
                sector_score=float(sector_score) if sector_score is not None else None,
                setup_tier=setup_tier,
                model_version=model_version
            ))
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
        ohlcv = session.query(models.OHLCV).filter_by(symbol=symbol).order_by(models.OHLCV.date.desc()).first()
        last_close = float(ohlcv.close) * PRICE_SCALE if ohlcv else None
        if score.setup_status in ('INVALID_PHASE', 'LOW_LIQUIDITY', 'DATA_ERROR', 'RR_REJECTED', 'NO_TRADE_PLAN'):
            entry_val, stop_val, target_val, rr_val = (last_close, None, None, None)
        else:
            entry_val, stop_val, target_val, rr_val = _compute_trade_params(session, symbol, last_close, feature)
        setup_quality_val = score.score * rr_val if rr_val is not None else None
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
                'ma200': getattr(feature, 'ma200', None),
                'ma20_slope': getattr(feature, 'ma20_slope', None),
                'ma50_slope': getattr(feature, 'ma50_slope', None),
                'ma100_slope': getattr(feature, 'ma100_slope', None),
                'ma200_slope': getattr(feature, 'ma200_slope', None),
                'avg_volume_20': feature.avg_volume_20,
                'avg_value_20': feature.avg_value_20,
                'volume_trend_5': getattr(feature, 'volume_trend_5', None),
                'atr_percent': getattr(feature, 'atr_percent', None),
                'liquidity_score': feature.liquidity_score,
                'liquidity_percentile_rank': feature.liquidity_percentile_rank,
                'rs_score': feature.rs_score,
                'sector_return_20d': feature.sector_return_20d,
                'sector_rs_vs_index': feature.sector_rs_vs_index,
                'sector_volume_momentum': feature.sector_volume_momentum,
                'sector_breadth_pct': feature.sector_breadth_pct,
                'sector_score': getattr(feature, 'sector_score', None)
            },
            regime=score.regime,
            score=score.score,
            suggested_trade={
                'action': score.setup_status,
                'entry': entry_val,
                'stop': stop_val,
                'target': target_val,
                'rr': rr_val,
                'setup_quality': setup_quality_val,
                'confidence': score.confidence,
                'market_alignment': score.market_alignment,
                'trade_signal': getattr(score, 'trade_signal', None),
                'sector_score': getattr(score, 'sector_score', None),
                'setup_tier': score.setup_tier,
                'model_version': score.model_version
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
            last_close_date = None
            pnl_vnd = None
            entry = None
            target = None
            stop = None
            rr_val = None
            buy_zone_low = None
            buy_zone_high = None
            take_profit = None
            if stock:
                score = session.query(models.StockScore).filter_by(stock_id=stock.id).order_by(models.StockScore.date.desc()).first()
                if score:
                    latest_score = score.score
                    latest_regime = score.regime
                    buy_zone_low = score.buy_zone_low
                    buy_zone_high = score.buy_zone_high
                    take_profit = score.tp_zone
                    if score.regime == 'MARKDOWN':
                        warning = 'Holding moved to MARKDOWN'
                    elif score.setup_status == 'LOW_LIQUIDITY':
                        warning = 'Holding is LOW_LIQUIDITY'
                ohlcv = session.query(models.OHLCV).filter_by(symbol=item.symbol).order_by(models.OHLCV.date.desc()).first()
                if ohlcv:
                    # OHLCV.close stored in thousands; convert to full price
                    last_close = float(ohlcv.close) * PRICE_SCALE
                    last_close_date = ohlcv.date
                    pnl_vnd = (last_close - float(item.avg_price)) * float(item.quantity)
                    if score and score.setup_status in ('INVALID_PHASE', 'LOW_LIQUIDITY', 'DATA_ERROR', 'RR_REJECTED', 'NO_TRADE_PLAN'):
                        entry, stop, target, rr_val = (last_close, None, None, None)
                    else:
                        # compute trade params fresh using full price
                        entry, stop, target, rr_val = _compute_trade_params(session, item.symbol, last_close, stock and session.query(models.StockFeatures).filter_by(stock_id=stock.id).order_by(models.StockFeatures.date.desc()).first())
            output.append(PortfolioItemOut(
                symbol=item.symbol,
                quantity=item.quantity,
                avg_price=item.avg_price,
                latest_regime=latest_regime,
                latest_score=latest_score,
                warning=warning,
                last_close=last_close,
                last_close_date=last_close_date,
                pnl_vnd=pnl_vnd,
                entry=entry,
                stop=stop,
                target=target,
                rr=rr_val,
                buy_zone_low=buy_zone_low,
                buy_zone_high=buy_zone_high,
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
        last_close_date = None
        pnl_vnd = None
        entry = None
        target = None
        buy_zone_low = None
        buy_zone_high = None
        take_profit = None
        if stock:
            score = session.query(models.StockScore).filter_by(stock_id=stock.id).order_by(models.StockScore.date.desc()).first()
            if score:
                latest_score = score.score
                latest_regime = score.regime
                buy_zone_low = score.buy_zone_low
                buy_zone_high = score.buy_zone_high
                take_profit = score.tp_zone
                entry = score.buy_zone_low
                target = score.tp_zone
                if score.regime == 'MARKDOWN':
                    warning = 'Holding moved to MARKDOWN'
            ohlcv = session.query(models.OHLCV).filter_by(symbol=symbol).order_by(models.OHLCV.date.desc()).first()
            if ohlcv:
                last_close = float(ohlcv.close) * PRICE_SCALE
                last_close_date = ohlcv.date
                pnl_vnd = (last_close - float(item.avg_price)) * float(item.quantity)

        return PortfolioItemOut(
            symbol=item.symbol,
            quantity=item.quantity,
            avg_price=item.avg_price,
            latest_regime=latest_regime,
            latest_score=latest_score,
            warning=warning,
            last_close=last_close,
            last_close_date=last_close_date,
            pnl_vnd=pnl_vnd,
            entry=entry,
            target=target,
            buy_zone_low=buy_zone_low,
            buy_zone_high=buy_zone_high,
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
        last_close_date = None
        pnl_vnd = None
        entry = None
        target = None
        buy_zone_low = None
        buy_zone_high = None
        take_profit = None
        if stock:
            score = session.query(models.StockScore).filter_by(stock_id=stock.id).order_by(models.StockScore.date.desc()).first()
            if score:
                latest_score = score.score
                latest_regime = score.regime
                buy_zone_low = score.buy_zone_low
                buy_zone_high = score.buy_zone_high
                take_profit = score.tp_zone
                entry = score.buy_zone_low
                target = score.tp_zone
                if score.regime == 'MARKDOWN':
                    warning = 'Holding moved to MARKDOWN'
            ohlcv = session.query(models.OHLCV).filter_by(symbol=item.symbol).order_by(models.OHLCV.date.desc()).first()
            if ohlcv:
                last_close = float(ohlcv.close) * PRICE_SCALE
                last_close_date = ohlcv.date
                pnl_vnd = (last_close - float(item.avg_price)) * float(item.quantity)

        return PortfolioItemOut(
            symbol=item.symbol,
            quantity=item.quantity,
            avg_price=item.avg_price,
            latest_regime=latest_regime,
            latest_score=latest_score,
            warning=warning,
            last_close=last_close,
            last_close_date=last_close_date,
            pnl_vnd=pnl_vnd,
            entry=entry,
            target=target,
            buy_zone_low=buy_zone_low,
            buy_zone_high=buy_zone_high,
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
