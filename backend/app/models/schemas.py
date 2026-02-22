from datetime import date
from pydantic import BaseModel
from typing import List, Optional


class MarketRegimeOut(BaseModel):
    regime: str
    confidence: float
    date: Optional[date] = None


class StockTopOut(BaseModel):
    symbol: str
    regime: str
    score: float
    buy_zone: str
    take_profit: str
    risk_reward: float


class StockDetailOut(BaseModel):
    symbol: str
    features: dict
    regime: str
    score: float
    suggested_trade: dict


class ScanLatestOut(BaseModel):
    date: date
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


class BacktestOut(BaseModel):
    symbol: str
    strategy: str
    win_rate: float
    max_drawdown: float
    avg_rr: float
    equity_curve: list
