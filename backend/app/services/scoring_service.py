import logging
import math
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from app.models import models
from app.utils.config import settings
from app.services import cycle_service

logger = logging.getLogger(__name__)


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

    # Attempt cycle-based phase detection using past data only
    try:
        window = max(int(getattr(settings, 'lookback_min', 150)), 120)
        cycle = cycle_service.compute_cycle_for_series(df['close'], window=window)
    except Exception:
        cycle = None

    if not cycle or not np.isfinite(cycle.get('cycle_phase', np.nan)):
        # Fallback to legacy rule-based classification when cycle unavailable
        regime = classify_regime(
            df,
            rs_score=rs_score,
            va_score=va_score,
            breadth20_pct=breadth20_pct,
            breadth50_pct=breadth50_pct
        )
        return {'phase': regime, 'rs_score': rs_score, 'va_score': va_score}

    phase = float(cycle.get('cycle_phase', float('nan')))
    amplitude = float(cycle.get('cycle_amplitude', float('nan')))
    dom_period = float(cycle.get('dominant_period', float('nan')))

    # Convert phase to degrees in [-180,180]
    deg = np.degrees(phase)

    # Compute a simple amplitude-to-volatility ratio to distinguish strong cycles
    last_price = float(df['close'].iloc[-1])
    vol_price = float(df['close'].pct_change().dropna().tail(20).std() * last_price) if len(df) >= 5 else 0.0
    amp_rel = amplitude / vol_price if vol_price and np.isfinite(amplitude) else 0.0

    # Map angle quadrants to regime labels (no lookahead)
    # -90..0: rising from trough -> accumulation
    # 0..90: approaching peak -> markup
    # 90..180: falling from peak -> distribution
    # -180..-90: deep fall -> markdown
    regime = None
    if -90.0 <= deg < 0.0:
        # Determine strength
        if amp_rel > 0.8 and rs_score > 0 and va_score > 0 and breadth20_pct >= 40 and breadth50_pct >= 30:
            regime = 'ACCUMULATION_STRONG'
        else:
            regime = 'ACCUMULATION_WEAK'
    elif 0.0 <= deg < 90.0:
        regime = 'MARKUP'
    elif 90.0 <= deg <= 180.0:
        regime = 'DISTRIBUTION'
    else:
        regime = 'MARKDOWN'

    return {'phase': regime, 'rs_score': rs_score, 'va_score': va_score}


def validate_signal_output(score_data: dict):
    """Quick sanity check on the generated signal.

    The trading engine is expected to emit a signal for every stock (unless the
    last close price is non‑positive).  We only verify that the core numeric
    fields exist and are finite/positive.  No hard filters or setup status
    thresholds are applied here.
    """
    if not score_data:
        return False, 'missing_score'

    issues = []

    # numeric fields that must be present and finite
    for key in ('score', 'confidence', 'entry', 'stop', 'target', 'rr'):
        value = score_data.get(key)
        if value is None or not np.isfinite(value):
            issues.append(f'invalid_{key}')
        elif isinstance(value, (int, float)) and value <= 0:
            issues.append(f'nonpositive_{key}')

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
    """Soft‐scoring system with 0–100 score distribution.
    
    Goal: produce 5–20 VALID scores per scan with proper scaling.
    Setup status determined ONLY by score thresholds:
      > 65: VALID
      45–65: WATCH
      < 45: IGNORE
    """

    last = df.iloc[-1]
    close = float(last['close'])

    # skip nonsensical data
    if close <= 0:
        logger.warning(f"{symbol}: non‑positive close ({close}), skipping signal")
        return None

    rolling_20_high = df['high'].rolling(20).max().iloc[-1]
    if not np.isfinite(rolling_20_high) or rolling_20_high <= 0:
        rolling_20_high = close

    rolling_20_low = df['low'].rolling(20).min().iloc[-1]
    if not np.isfinite(rolling_20_low) or rolling_20_low <= 0:
        rolling_20_low = close * 0.95

    # phase/regime context
    if phase_context is None:
        phase_context = detect_stock_phase(
            df,
            vni_df,
            breadth20_pct=breadth20_pct,
            breadth50_pct=breadth50_pct
        )
    regime = phase_context['phase']

    # component scores (all 0..10 scale)
    technical = technical_score_0_10(df)
    rs_0_10 = rs_score_0_10(df, vni_df)
    liquidity_score = df['liquidity_score'].iloc[-1] if 'liquidity_score' in df.columns else 5.0
    if not np.isfinite(liquidity_score):
        liquidity_score = 5.0

    sector_score = 0.0
    if sector_context is not None:
        sector_ret = sector_context.get('sector_return_20d', 0.0)
        sector_vol = sector_context.get('sector_volume_momentum', 0.0)
        sector_breadth = sector_context.get('sector_breadth_pct', 0.0)
        vni_ret20 = vni_df['close'].pct_change(20).iloc[-1]
        if pd.notna(vni_ret20) and sector_ret > vni_ret20:
            sector_score += 3
        if sector_vol > 0:
            sector_score += 2
        if sector_breadth > 50:
            sector_score += 2
    sector_score = float(np.clip(sector_score, 0, 10))

    cycle_score_0_10 = 5.0
    cycle_phase_val = None
    if 'cycle_phase' in df.columns:
        try:
            cp = df['cycle_phase'].iloc[-1]
            if np.isfinite(cp):
                cycle_phase_val = float(cp)
                # Better cycle boost: favor bottoms (cos near +1), penalize tops (cos near -1)
                # cos(-pi) = -1 (top), cos(0) = 1 (bottom)
                cycle_cos = float(np.cos(cycle_phase_val))
                # map to 0..10 with boost at bottom
                cycle_score_0_10 = float(np.clip((cycle_cos + 1.0) / 2.0 * 10.0, 0.0, 10.0))
        except Exception:
            cycle_score_0_10 = 5.0

    # Weighted aggregation (all 0..10 scale)
    weights = {
        'technical': float(getattr(settings, 'weight_technical', 1.0)),
        'rs': float(getattr(settings, 'weight_rs', 1.0)),
        'liquidity': float(getattr(settings, 'weight_liquidity', 0.5)),
        'sector': float(getattr(settings, 'weight_sector', 0.5)),
        'cycle': float(getattr(settings, 'weight_cycle', 1.0))
    }
    weight_sum = sum(weights.values())
    if weight_sum <= 0:
        weights = {k: 1.0 for k in weights}
        weight_sum = len(weights)

    comp_sum = (
        technical * weights['technical'] +
        rs_0_10 * weights['rs'] +
        liquidity_score * weights['liquidity'] +
        sector_score * weights['sector'] +
        cycle_score_0_10 * weights['cycle']
    )
    base_score_0_10 = comp_sum / weight_sum
    score_value = float(np.clip(base_score_0_10 * 10.0, 0.0, 100.0))

    # Breakout strength bonus (0..20 points)
    breakout_strength = max(0.0, (close / rolling_20_high - 1.0) * 100.0)
    breakout_bonus = min(20.0, breakout_strength * 0.2)  # up to +20
    score_value += breakout_bonus

    # Regime multipliers (no penalties, only boosts)
    if market_regime == 'MARKUP':
        score_value *= 1.15
    elif market_regime == 'ACCUMULATION' or market_regime == 'ACCUMULATION_STRONG':
        score_value *= 1.10
    elif market_regime == 'ACCUMULATION_WEAK':
        score_value *= 1.05
    # DISTRIBUTION/MARKDOWN: no boost (neutral * 1.0)

    # Volume spike penalty (weak extension)
    recent = df.tail(2)
    vol_spike_days = int((recent['volume_ratio'] > 1.5).sum()) if len(recent) == 2 else 0
    weak_extension = close < rolling_20_high * 1.01
    if close >= rolling_20_high and weak_extension and vol_spike_days <= 1:
        score_value *= 0.85  # 15% penalty

    # Price proximity to 20-high/low (favor mid-range breakouts over exhausted moves)
    mid_range = (rolling_20_high + rolling_20_low) / 2.0
    dist_from_mid = abs(close - mid_range) / (rolling_20_high - rolling_20_low + 0.01)
    if dist_from_mid > 0.4:  # too close to extreme
        score_value *= 0.9

    score_value = float(np.clip(score_value, 0.0, 100.0))
    confidence = score_value

    # Cycle boost at bottoms (strong)
    try:
        if cycle_phase_val is not None and np.isfinite(cycle_phase_val):
            cycle_cos = float(np.cos(cycle_phase_val))
            # strong boost near bottom (cos > 0.6)
            if cycle_cos > 0.6:
                score_value *= 1.15
            # penalty near top (cos < -0.6)
            elif cycle_cos < -0.6:
                score_value *= 0.80
    except Exception:
        pass

    # apply phase-based score reductions
    if regime == 'DISTRIBUTION':
        score_value *= 0.8
    elif regime == 'MARKDOWN':
        score_value *= 0.6

    score_value = float(np.clip(score_value, 0.0, 100.0))
    confidence = score_value

    market_alignment = 'NEUTRAL'
    if market_regime in ('MARKUP', 'ACCUMULATION', 'ACCUMULATION_STRONG', 'ACCUMULATION_WEAK'):
        market_alignment = 'ALIGNED'
    elif market_regime in ('DISTRIBUTION', 'MARKDOWN'):
        market_alignment = 'MISALIGNED'

    logger.debug(
        "%s score_breakdown tech=%.1f rs=%.1f liq=%.1f sect=%.1f cyc=%.1f breakout=+%.1f regime=%.0f final=%.1f",
        symbol, technical, rs_0_10, liquidity_score, sector_score,
        cycle_score_0_10, breakout_bonus, 100.0 if market_regime in ('MARKUP', 'ACCUMULATION') else 100.0, score_value
    )

    # map score into trading action (replaces old VALID/WATCH/IGNORE setup_status)
    if score_value >= 75:
        action = 'BUY'
    elif score_value >= 60:
        action = 'WATCH'
    else:
        action = 'AVOID'
    setup_status = action  # keep legacy key for database compatibility

    # build trade parameters: always compute using ATR (or fallback)
    atr_val = float(last['atr']) if pd.notna(last.get('atr')) and last['atr'] > 0 else None
    if atr_val is None or not np.isfinite(atr_val) or atr_val <= 0:
        # try ma20 or 20-day range as surrogate
        ma20 = float(last.get('ma20')) if pd.notna(last.get('ma20')) else None
        if ma20 is not None and np.isfinite(ma20) and ma20 > 0:
            atr_val = ma20
        else:
            high_val = df['high'].rolling(20).max().iloc[-1]
            low_val = df['low'].rolling(20).min().iloc[-1]
            range_val = (high_val - low_val) / 3.5 if pd.notna(high_val) and pd.notna(low_val) else 1.0
            atr_val = float(range_val) if range_val > 0 else 1.0
    atr_val = max(atr_val, 1e-6)

    entry = close
    # dynamic multipliers based on breakout strength
    strength = max(0.0, (close / rolling_20_high - 1.0))
    target_mult = 2.0 + strength * 5.0
    stop_mult = 1.5

    stop = entry - stop_mult * atr_val
    target = entry + target_mult * atr_val
    # ensure positive
    if stop <= 0:
        stop = entry * 0.01
    if target <= 0:
        target = entry * 1.01

    rr = (target - entry) / max(entry - stop, 1e-6)
    setup_quality = score_value * rr

    setup_tier = None
    if np.isfinite(rr):
        if rr > 2.5:
            setup_tier = 'A'
        elif rr >= 1.5:
            setup_tier = 'B'
        else:
            setup_tier = 'C'
    # retain old buy_zone fields as None so DB save_score remains functional
    return {
        'regime': regime,
        'phase': regime,  # alias for clarity
        'action': action,
        'setup_status': setup_status,
        'market_alignment': market_alignment,
        'model_version': 'v3',
        'setup_tier': setup_tier,
        'confidence': confidence,
        'score': score_value,
        'setup_quality': setup_quality,
        'entry': entry,
        'stop': stop,
        'target': target,
        'rr': rr,
        'buy_zone_low': None,
        'buy_zone_high': None,
        'tp_zone': None,
        'stop_loss': stop,
        'risk_reward': rr
    }


def save_score(session: Session, symbol: str, date, score_data):
    stock = session.query(models.Stock).filter_by(symbol=symbol).first()
    if not stock:
        return
    exists = session.query(models.StockScore).filter_by(stock_id=stock.id, date=date).first()
    if exists:
        exists.regime = score_data['regime']
        exists.score = score_data['score']
        exists.buy_zone_low = score_data.get('buy_zone_low')
        exists.buy_zone_high = score_data.get('buy_zone_high')
        exists.tp_zone = score_data.get('tp_zone')
        exists.stop_loss = score_data.get('stop_loss')
        exists.risk_reward = score_data.get('risk_reward')
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
            buy_zone_low=score_data.get('buy_zone_low'),
            buy_zone_high=score_data.get('buy_zone_high'),
            tp_zone=score_data.get('tp_zone'),
            stop_loss=score_data.get('stop_loss'),
            risk_reward=score_data.get('risk_reward'),
            confidence=score_data['confidence'],
            setup_status=score_data.get('setup_status'),
            market_alignment=score_data.get('market_alignment'),
            model_version=score_data.get('model_version'),
            setup_tier=score_data.get('setup_tier')
        ))
    session.commit()
