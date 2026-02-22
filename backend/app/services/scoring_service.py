import math
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from app.models import models
from app.utils.config import settings


def _round_zone(values):
    return f"{values[0]:.2f}-{values[1]:.2f}"


def classify_regime(df: pd.DataFrame):
    last = df.iloc[-1]
    close = last['close']
    ma20 = last['ma20']
    ma50 = last['ma50']
    ma100 = last['ma100']
    rsi = last['rsi']
    adx = last['adx']
    atr = last['atr']
    volume_ratio = last['volume_ratio']

    rolling_20_high = df['high'].rolling(20).max().iloc[-1]
    rolling_15_high = df['high'].rolling(15).max().iloc[-1]
    rolling_15_low = df['low'].rolling(15).min().iloc[-1]

    breakout = close > rolling_20_high * 1.001
    volume_spike = volume_ratio > 1.5
    price_above_ma100 = close > ma100
    tight_range = (rolling_15_high - rolling_15_low) / close < 0.06
    volume_contraction = volume_ratio < 0.8
    atr_contract = atr < df['atr'].rolling(20).mean().iloc[-1]

    markdown = (close < ma50) and (rsi < 40) and (volume_ratio > 1.2)
    distribution = (rsi > 70) and (volume_spike) and (close < rolling_15_high * 0.995)
    markup = breakout and volume_spike and (adx > 25) and (rsi > 60)
    accumulation = price_above_ma100 and (40 <= rsi <= 55) and volume_contraction and atr_contract and tight_range

    if markup:
        return 'MARKUP'
    if markdown:
        return 'MARKDOWN'
    if distribution:
        return 'DISTRIBUTION'
    if accumulation:
        return 'ACCUMULATION'
    return 'ACCUMULATION'


def volume_momentum_score(df: pd.DataFrame):
    last = df.iloc[-1]
    vr = last['volume_ratio']
    trend = df['volume'].rolling(5).mean().iloc[-1] / df['volume'].rolling(20).mean().iloc[-1]
    score = (vr - 1.0) * 12 + (trend - 1.0) * 10
    return float(np.clip(score, -10, 15))


def relative_strength_score(stock_df: pd.DataFrame, vni_df: pd.DataFrame):
    stock_ret = stock_df['close'].pct_change(20).iloc[-1]
    vni_ret = vni_df['close'].pct_change(20).iloc[-1]
    rs = (stock_ret - vni_ret) * 100
    return float(np.clip(rs, -10, 15))


def build_trade_zones(last_close: float, atr: float):
    buy_zone = (last_close - 0.5 * atr, last_close + 0.5 * atr)
    stop_loss = last_close - 1.5 * atr
    take_profit = last_close + 3.0 * atr
    rr = (take_profit - last_close) / max(last_close - stop_loss, 0.01)
    return buy_zone, take_profit, stop_loss, rr


def score_stock(session: Session, symbol: str, df: pd.DataFrame, vni_df: pd.DataFrame, market_regime: str):
    last = df.iloc[-1]
    avg_vol = df['volume'].rolling(20).mean().iloc[-1]
    if math.isnan(avg_vol) or avg_vol < settings.liquidity_min_avg_volume:
        return {
            'regime': 'LOW_LIQUIDITY',
            'confidence': 0.0,
            'score': 0.0,
            'buy_zone': '',
            'tp_zone': '',
            'stop_loss': '',
            'risk_reward': 0.0
        }

    regime = classify_regime(df)
    base = 50.0
    if regime == 'ACCUMULATION':
        base = 55.0
    elif regime == 'MARKUP':
        base = 65.0
        if market_regime == 'MARKUP':
            base += 5.0
    elif regime == 'DISTRIBUTION':
        base = 40.0
    elif regime == 'MARKDOWN':
        base = 30.0

    vm_score = volume_momentum_score(df)
    rs_score = relative_strength_score(df, vni_df)
    confidence = float(np.clip(base + vm_score + rs_score, 0, 100))

    buy_zone, tp, stop, rr = build_trade_zones(float(last['close']), float(last['atr']))
    return {
        'regime': regime,
        'confidence': confidence,
        'score': confidence,
        'buy_zone': _round_zone(buy_zone),
        'tp_zone': f"{tp:.2f}",
        'stop_loss': f"{stop:.2f}",
        'risk_reward': float(rr)
    }


def save_score(session: Session, symbol: str, date, score_data):
    stock = session.query(models.Stock).filter_by(symbol=symbol).first()
    if not stock:
        return
    exists = session.query(models.StockScore).filter_by(stock_id=stock.id, date=date).first()
    if exists:
        return
    session.add(models.StockScore(
        stock_id=stock.id,
        date=date,
        regime=score_data['regime'],
        score=score_data['score'],
        buy_zone=score_data['buy_zone'],
        tp_zone=score_data['tp_zone'],
        stop_loss=score_data['stop_loss'],
        risk_reward=score_data['risk_reward'],
        confidence=score_data['confidence']
    ))
    session.commit()
