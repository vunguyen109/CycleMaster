from datetime import date as dt_date
from pydantic import BaseModel
from typing import List, Optional


class MarketRegimeOut(BaseModel):
    regime: str
    confidence: float
    date: Optional[dt_date] = None
    prev_regime: Optional[str] = None
    prev_confidence: Optional[float] = None
    confidence_change: Optional[float] = None


class StockTopOut(BaseModel):
    symbol: str
    regime: str
    score: float
    last_close: Optional[float] = None
    # legacy fields retained for backward compatibility
    buy_zone_low: Optional[float] = None
    buy_zone_high: Optional[float] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    risk_reward: Optional[float] = None
    # new trading signal fields
    action: Optional[str] = None
    entry: Optional[float] = None
    stop: Optional[float] = None
    target: Optional[float] = None
    rr: Optional[float] = None
    setup_quality: Optional[float] = None
    liquidity_score: Optional[float] = None
    setup_status: Optional[str] = None
    market_alignment: Optional[str] = None
    trade_signal: Optional[str] = None
    sector_score: Optional[float] = None
    setup_tier: Optional[str] = None
    model_version: Optional[str] = None


class StockDetailOut(BaseModel):
    symbol: str
    features: dict
    regime: str
    score: float
    suggested_trade: dict  # will contain action, entry/stop/target, rr, etc


class ScanLatestOut(BaseModel):
    date: dt_date
    total_scanned: int
    top_symbols: List[str]
    market_regime: str


class AlertOut(BaseModel):
    symbol: str
    regime: str
    confidence: float
    reason: str


class PortfolioItemOut(BaseModel):
    symbol: str
    quantity: float
    avg_price: float
    latest_regime: Optional[str] = None
    latest_score: Optional[float] = None
    warning: Optional[str] = None
    last_close: Optional[float] = None
    last_close_date: Optional[dt_date] = None
    pnl_vnd: Optional[float] = None
    entry: Optional[float] = None
    stop: Optional[float] = None
    target: Optional[float] = None
    rr: Optional[float] = None
    buy_zone_low: Optional[float] = None
    buy_zone_high: Optional[float] = None
    take_profit: Optional[float] = None


class PortfolioUpsertIn(BaseModel):
    symbol: str
    quantity: float
    avg_price: float


class BacktestOut(BaseModel):
    symbol: str
    strategy: str
    win_rate: float
    max_drawdown: float
    avg_rr: float
    equity_curve: list


class MarketSeriesPoint(BaseModel):
    date: dt_date
    close: float


class MarketSeriesOut(BaseModel):
    symbol: str
    series: List[MarketSeriesPoint]
