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
    buy_zone: Optional[str] = None
    take_profit: Optional[str] = None
    stop_loss: Optional[str] = None
    risk_reward: Optional[float] = None
    liquidity_score: Optional[float] = None
    setup_status: Optional[str] = None
    market_alignment: Optional[str] = None
    setup_tier: Optional[str] = None


class StockDetailOut(BaseModel):
    symbol: str
    features: dict
    regime: str
    score: float
    suggested_trade: dict


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
    pnl_vnd: Optional[float] = None
    buy_zone: Optional[str] = None
    take_profit: Optional[str] = None


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
