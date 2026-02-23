import math
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from app.models import models
from app.utils.config import settings


def _round_zone(values):
    return f"{values[0]:.2f}-{values[1]:.2f}"


def classify_regime(
    df: pd.DataFrame,
    rs_score: float = 0.0,
    va_score: float = 0.0,
    breadth20_pct: float = 100.0,
    breadth50_pct: float = 100.0
):
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
    adx_weak = adx < 20
    atr_slope = df['atr'].diff(5).iloc[-1]

    markdown = (close < ma50) and (rsi < 40) and (volume_ratio > 1.2)
    distribution = (rsi > 70) and (volume_spike) and (close < rolling_15_high * 0.995)
    markup = breakout and volume_spike and (adx > 25) and (rsi > 60)
    down_day = last['close'] < last['open']
    accumulation = price_above_ma100 and (42 <= rsi <= 55) and volume_contraction and atr_contract and tight_range
    accumulation &= not (rsi < 40 or rsi > 65)
    accumulation &= not (close < ma50)
    accumulation &= not (volume_spike and down_day)
    accumulation &= adx_weak
    accumulation &= atr_slope <= 0

    if markup:
        return 'MARKUP'
    if markdown:
        return 'MARKDOWN'
    if distribution:
        return 'DISTRIBUTION'
    if accumulation:
        if rs_score > 0 and va_score > 0 and breadth20_pct >= 40 and breadth50_pct >= 30:
            return 'ACCUMULATION_STRONG'
        return 'ACCUMULATION_WEAK'
    return 'ACCUMULATION_WEAK'


def volume_momentum_score(df: pd.DataFrame):
    last = df.iloc[-1]
    vr = last['volume_ratio']
    trend = df['volume'].rolling(5).mean().iloc[-1] / df['volume'].rolling(20).mean().iloc[-1]
    score = (vr - 1.0) * 12 + (trend - 1.0) * 10
    return float(np.clip(score, -10, 15))


def volume_accumulation_score(df: pd.DataFrame):
    if len(df) < 25:
        return 0.0
    vol_ma5 = df['volume'].rolling(5).mean().iloc[-1]
    vol_ma20 = df['volume'].rolling(20).mean().iloc[-1]
    price_change_5d = abs(df['close'].pct_change(5).iloc[-1])
    if pd.isna(vol_ma5) or pd.isna(vol_ma20) or pd.isna(price_change_5d):
        return 0.0
    vol_trend = vol_ma5 / max(vol_ma20, 1)
    score = (vol_trend - 1.0) * 10 - price_change_5d * 50
    return float(np.clip(score, -5, 10))


def relative_strength_score(stock_df: pd.DataFrame, vni_df: pd.DataFrame):
    stock_ret = stock_df['close'].pct_change(20).iloc[-1]
    vni_ret = vni_df['close'].pct_change(20).iloc[-1]
    rs = (stock_ret - vni_ret) * 100
    return float(np.clip(rs, -10, 15))


def rs_score_0_10(stock_df: pd.DataFrame, vni_df: pd.DataFrame):
    stock_ret = stock_df['close'].pct_change(20).iloc[-1]
    vni_ret = vni_df['close'].pct_change(20).iloc[-1]
    rs_pct = (stock_ret - vni_ret) * 100
    score = (rs_pct + 10) / 20 * 10
    return float(np.clip(score, 0, 10))


def _linear_score(value: float, low: float, high: float):
    if value is None or not np.isfinite(value):
        return 0.0
    if value <= low:
        return 0.0
    if value >= high:
        return 10.0
    return float((value - low) / (high - low) * 10)


def rsi_score_0_10(rsi: float):
    if rsi is None or not np.isfinite(rsi):
        return 0.0
    anchors = [
        (20, 0),
        (30, 8),
        (45, 8),
        (55, 10),
        (65, 6),
        (80, 0)
    ]
    if rsi <= anchors[0][0]:
        return 0.0
    if rsi >= anchors[-1][0]:
        return 0.0
    for (x1, y1), (x2, y2) in zip(anchors, anchors[1:]):
        if x1 <= rsi <= x2:
            if x2 == x1:
                return float(y1)
            return float(y1 + (y2 - y1) * (rsi - x1) / (x2 - x1))
    return 0.0


def macd_score_0_10(df: pd.DataFrame):
    macd_hist = df['macd'].iloc[-1]
    if macd_hist is None or not np.isfinite(macd_hist):
        return 0.0
    scale = df['macd'].rolling(20).std().iloc[-1]
    scale = float(scale) if np.isfinite(scale) and scale > 0 else max(abs(macd_hist), 1e-6)
    score = 5 + 5 * np.tanh(macd_hist / scale)
    return float(np.clip(score, 0, 10))


def adx_score_0_10(adx: float):
    if adx is None or not np.isfinite(adx):
        return 0.0
    if adx <= 10:
        return 0.0
    if adx >= 30:
        return 10.0
    return float((adx - 10) / 20 * 10)


def ma_alignment_score_0_10(close: float, ma20: float, ma50: float, ma100: float):
    scores = []
    for ma in (ma20, ma50, ma100):
        if ma is None or not np.isfinite(ma) or ma == 0:
            scores.append(0.0)
            continue
        ratio = (close / ma) - 1.0
        scores.append(_linear_score(ratio, -0.05, 0.05))
    return float(np.clip(np.mean(scores), 0, 10))


def volume_momentum_score_0_10(df: pd.DataFrame):
    if len(df) < 25:
        return 0.0
    vol_ma5 = df['volume'].rolling(5).mean().iloc[-1]
    vol_ma20 = df['volume'].rolling(20).mean().iloc[-1]
    if not np.isfinite(vol_ma5) or not np.isfinite(vol_ma20) or vol_ma20 == 0:
        return 0.0
    vol_trend = vol_ma5 / vol_ma20
    trend_score = _linear_score(vol_trend, 0.8, 1.5)
    accum_raw = volume_accumulation_score(df)
    accum_score = float(np.clip((accum_raw + 5) / 15 * 10, 0, 10))
    score = 0.6 * trend_score + 0.4 * accum_score
    return float(np.clip(score, 0, 10))


def technical_score_0_10(df: pd.DataFrame):
    last = df.iloc[-1]
    rsi_s = rsi_score_0_10(float(last['rsi']))
    macd_s = macd_score_0_10(df)
    adx_s = adx_score_0_10(float(last['adx']))
    ma_s = ma_alignment_score_0_10(float(last['close']), float(last['ma20']), float(last['ma50']), float(last['ma100']))
    vol_s = volume_momentum_score_0_10(df)
    score = (rsi_s + macd_s + adx_s + ma_s + vol_s) / 5
    return float(np.clip(score, 0, 10))


def detect_stock_phase(
    df: pd.DataFrame,
    vni_df: pd.DataFrame,
    breadth20_pct: float = 100.0,
    breadth50_pct: float = 100.0
):
    rs_score = relative_strength_score(df, vni_df)
    va_score = volume_accumulation_score(df)
    regime = classify_regime(
        df,
        rs_score=rs_score,
        va_score=va_score,
        breadth20_pct=breadth20_pct,
        breadth50_pct=breadth50_pct
    )
    return {
        'phase': regime,
        'rs_score': rs_score,
        'va_score': va_score
    }


def validate_signal_output(score_data: dict):
    if not score_data:
        return False, 'missing_score'
    issues = []
    for key in ('score', 'confidence'):
        value = score_data.get(key)
        if value is None or not np.isfinite(value):
            issues.append(f'invalid_{key}')
    setup_status = score_data.get('setup_status')
    if setup_status == 'VALID':
        rr = score_data.get('risk_reward')
        if rr is None or not np.isfinite(rr):
            issues.append('invalid_risk_reward')
        for key in ('buy_zone', 'tp_zone', 'stop_loss'):
            value = score_data.get(key)
            if value is None or (isinstance(value, str) and value.strip() == ''):
                issues.append(f'missing_{key}')
        if isinstance(rr, (int, float)) and rr < 0:
            issues.append('negative_risk_reward')
    if issues:
        return False, ','.join(issues)
    return True, ''


def build_trade_zones(entry: float, atr: float):
    if atr is None or not np.isfinite(atr) or atr <= 0:
        return None, None, None, None
    buy_zone = (entry - 0.5 * atr, entry + 0.5 * atr)
    stop_loss = entry - 1.5 * atr
    take_profit = entry + 2.5 * atr
    rr = (take_profit - entry) / max(entry - stop_loss, 0.01)
    return buy_zone, take_profit, stop_loss, rr


def score_stock(
    session: Session,
    symbol: str,
    df: pd.DataFrame,
    vni_df: pd.DataFrame,
    market_regime: str,
    breadth20_pct: float = 100.0,
    breadth50_pct: float = 100.0,
    phase_context: dict | None = None,
    sector_context: dict | None = None
):
    last = df.iloc[-1]
    avg_vol = df['volume'].rolling(20).mean().iloc[-1]
    avg_value = (df['close'] * df['volume']).rolling(20).mean().iloc[-1]
    rolling_20_high = df['high'].rolling(20).max().iloc[-1]
    if not np.isfinite(rolling_20_high):
        rolling_20_high = last['high']
    if math.isnan(avg_vol) or avg_vol < settings.liquidity_min_avg_volume:
        return {
            'regime': 'NEUTRAL',
            'setup_status': 'LOW_LIQUIDITY',
            'market_alignment': 'NEUTRAL',
            'model_version': 'v2',
            'setup_tier': None,
            'confidence': 0.0,
            'score': 0.0,
            'buy_zone': None,
            'tp_zone': None,
            'stop_loss': None,
            'risk_reward': 0.0
        }
    if math.isnan(avg_value) or avg_value < settings.liquidity_min_avg_value:
        return {
            'regime': 'NEUTRAL',
            'setup_status': 'LOW_LIQUIDITY',
            'market_alignment': 'NEUTRAL',
            'model_version': 'v2',
            'setup_tier': None,
            'confidence': 0.0,
            'score': 0.0,
            'buy_zone': None,
            'tp_zone': None,
            'stop_loss': None,
            'risk_reward': 0.0
        }

    if phase_context is None:
        phase_context = detect_stock_phase(
            df,
            vni_df,
            breadth20_pct=breadth20_pct,
            breadth50_pct=breadth50_pct
        )
    regime = phase_context['phase']
    rs_score = phase_context['rs_score']
    va_score = phase_context['va_score']
    technical = technical_score_0_10(df)
    rs_0_10 = rs_score_0_10(df, vni_df)
    liquidity_score = df['liquidity_score'].iloc[-1] if 'liquidity_score' in df.columns else 0.0
    if not np.isfinite(liquidity_score):
        liquidity_score = 0.0
    sector_score = 0.0
    if sector_context is not None:
        sector_ret = sector_context.get('sector_return_20d', 0.0)
        sector_vol = sector_context.get('sector_volume_momentum', 0.0)
        sector_breadth = sector_context.get('sector_breadth_pct', 0.0)
        vni_ret20 = vni_df['close'].pct_change(20).iloc[-1]
        if pd.notna(vni_ret20) and sector_ret > vni_ret20:
            sector_score += 4
        if sector_vol > 0:
            sector_score += 3
        if sector_breadth > 55:
            sector_score += 3
    sector_score = float(np.clip(sector_score, 0, 10))

    final_score_0_10 = (
        (technical * settings.weight_technical) +
        (rs_0_10 * settings.weight_rs) +
        (liquidity_score * settings.weight_liquidity) +
        (sector_score * settings.weight_sector)
    )
    score_value = float(np.clip(final_score_0_10 * 10, 0, 100))
    market_alignment = 'NEUTRAL'
    if market_regime in ('MARKUP', 'ACCUMULATION'):
        market_alignment = 'ALIGNED'
    elif market_regime in ('DISTRIBUTION', 'MARKDOWN'):
        market_alignment = 'MISALIGNED'

    if market_regime == 'MARKUP':
        score_value = float(np.clip(score_value * 1.1, 0, 100))
    elif market_regime == 'ACCUMULATION':
        score_value = float(np.clip(score_value * 1.05, 0, 100))
    elif market_regime == 'DISTRIBUTION':
        score_value = float(np.clip(score_value * 0.8, 0, 100))
    elif market_regime == 'MARKDOWN':
        score_value = float(np.clip(score_value * 0.7, 0, 100))
    confidence = score_value

    if regime in ('DISTRIBUTION', 'MARKDOWN'):
        return {
            'regime': regime,
            'setup_status': 'INVALID',
            'market_alignment': market_alignment,
            'model_version': 'v2',
            'setup_tier': None,
            'confidence': confidence,
            'score': score_value,
            'buy_zone': None,
            'tp_zone': None,
            'stop_loss': None,
            'risk_reward': None
        }

    # Fake breakout filter
    breakout_level = rolling_20_high
    close_above_breakout = float(last['close']) >= breakout_level
    weak_extension = float(last['close']) < breakout_level * 1.01
    recent = df.tail(2)
    if len(recent) == 2:
        vol_spike_days = (recent['volume_ratio'] > 1.5).sum()
    else:
        vol_spike_days = 0
    if close_above_breakout and weak_extension and vol_spike_days <= 1:
        score_value = float(np.clip(score_value * 0.7, 0, 100))
        confidence = float(np.clip(confidence * 0.7, 0, 100))

    breakout_level = rolling_20_high
    is_breakout = float(last['close']) >= breakout_level
    if sector_context is not None:
        vni_ret20 = vni_df['close'].pct_change(20).iloc[-1]
        sector_ret20 = sector_context.get('sector_return_20d', 0.0)
        if pd.notna(vni_ret20) and sector_ret20 <= vni_ret20:
            is_breakout = False
    if not is_breakout:
        return {
            'regime': regime,
            'setup_status': 'NO_SETUP',
            'market_alignment': market_alignment,
            'model_version': 'v2',
            'setup_tier': None,
            'confidence': confidence,
            'score': score_value,
            'buy_zone': None,
            'tp_zone': None,
            'stop_loss': None,
            'risk_reward': None
        }

    buy_zone, tp, stop, rr = build_trade_zones(float(breakout_level), float(last['atr']))
    if buy_zone is None:
        return {
            'regime': regime,
            'setup_status': 'NO_SETUP',
            'market_alignment': market_alignment,
            'model_version': 'v2',
            'setup_tier': None,
            'confidence': confidence,
            'score': score_value,
            'buy_zone': None,
            'tp_zone': None,
            'stop_loss': None,
            'risk_reward': None
        }
    setup_tier = None
    if rr is not None and np.isfinite(rr):
        if rr > 2.5:
            setup_tier = 'A'
        elif rr >= 1.5:
            setup_tier = 'B'
        else:
            setup_tier = 'C'

    return {
        'regime': regime,
        'setup_status': 'VALID',
        'market_alignment': market_alignment,
        'model_version': 'v2',
        'setup_tier': setup_tier,
        'confidence': confidence,
        'score': score_value,
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
        exists.regime = score_data['regime']
        exists.score = score_data['score']
        exists.buy_zone = score_data['buy_zone']
        exists.tp_zone = score_data['tp_zone']
        exists.stop_loss = score_data['stop_loss']
        exists.risk_reward = score_data['risk_reward']
        exists.confidence = score_data['confidence']
        exists.setup_status = score_data.get('setup_status')
        exists.market_alignment = score_data.get('market_alignment')
        exists.model_version = score_data.get('model_version')
        exists.setup_tier = score_data.get('setup_tier')
    else:
        session.add(models.StockScore(
            stock_id=stock.id,
            date=date,
            regime=score_data['regime'],
            score=score_data['score'],
            buy_zone=score_data['buy_zone'],
            tp_zone=score_data['tp_zone'],
            stop_loss=score_data['stop_loss'],
            risk_reward=score_data['risk_reward'],
            confidence=score_data['confidence'],
            setup_status=score_data.get('setup_status'),
            market_alignment=score_data.get('market_alignment'),
            model_version=score_data.get('model_version'),
            setup_tier=score_data.get('setup_tier')
        ))
    session.commit()
