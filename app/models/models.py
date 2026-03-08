from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from .base import Base


class MarketRegime(Base):
    __tablename__ = 'market_regime'
    id = Column(Integer, primary_key=True)
    date = Column(Date, index=True)
    regime = Column(String, index=True)
    confidence = Column(Float)


class Stock(Base):
    __tablename__ = 'stocks'
    id = Column(Integer, primary_key=True)
    symbol = Column(String, unique=True, index=True)
    sector = Column(String, default='')


class OHLCV(Base):
    __tablename__ = 'ohlcv'
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    date = Column(Date, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    __table_args__ = (UniqueConstraint('symbol', 'date', name='uix_symbol_date'),)


class StockFeatures(Base):
    __tablename__ = 'stock_features'
    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey('stocks.id'))
    date = Column(Date, index=True)
    rsi = Column(Float)
    macd = Column(Float)
    adx = Column(Float)
    volume_ratio = Column(Float)
    atr = Column(Float)
    ma20 = Column(Float)
    ma50 = Column(Float)
    ma100 = Column(Float)
    ma200 = Column(Float)
    ma20_slope = Column(Float)
    ma50_slope = Column(Float)
    ma100_slope = Column(Float)
    ma200_slope = Column(Float)
    volume_trend_5 = Column(Float)
    atr_percent = Column(Float)
    avg_volume_20 = Column(Float)
    avg_value_20 = Column(Float)
    liquidity_score = Column(Float)
    liquidity_percentile_rank = Column(Float)
    rs_score = Column(Float)
    # Cycle features
    cycle_phase = Column(Float)
    cycle_amplitude = Column(Float)
    dominant_cycle_period = Column(Float)
    sector_return_20d = Column(Float)
    sector_rs_vs_index = Column(Float)
    sector_volume_momentum = Column(Float)
    sector_breadth_pct = Column(Float)
    sector_score = Column(Float)
    stock = relationship('Stock')
    __table_args__ = (UniqueConstraint('stock_id', 'date', name='uix_features_stock_date'),)


class StockScore(Base):
    __tablename__ = 'stock_scores'
    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey('stocks.id'))
    date = Column(Date, index=True)
    regime = Column(String)
    score = Column(Float)
    buy_zone_low = Column(Float)  # replaces string buy_zone
    buy_zone_high = Column(Float)
    tp_zone = Column(Float)
    stop_loss = Column(Float)
    risk_reward = Column(Float)
    confidence = Column(Float)
    setup_status = Column(String)
    market_alignment = Column(String)
    trade_signal = Column(String)
    sector_score = Column(Float)
    model_version = Column(String)
    setup_tier = Column(String)
    stock = relationship('Stock')
    __table_args__ = (UniqueConstraint('stock_id', 'date', name='uix_scores_stock_date'),)


class Portfolio(Base):
    __tablename__ = 'portfolio'
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    quantity = Column(Float)
    avg_price = Column(Float)


class DailyAiInsight(Base):
    __tablename__ = 'daily_ai_insights'
    id = Column(Integer, primary_key=True)
    date = Column(Date, index=True, unique=True)
    market_narrative = Column(String)
    sector_insight = Column(String)
    stock_reviews = Column(String)  # JSON string
    daily_newsletter = Column(String)
