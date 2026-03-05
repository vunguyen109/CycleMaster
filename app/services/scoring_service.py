import logging
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from app.models import models
from app.utils.config import settings
from app.services import cycle_service, signal_service, trade_service

logger = logging.getLogger(__name__)
MODEL_VERSION = 'v7.0-refactor'


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


def technical_score_v2_0_10(trend_score: float, volume_momentum_score: float, cycle_score: float):
    """V2 technical score: Trend 40%, Volume Momentum 30%, Cycle 30%."""
    t = float(np.clip(trend_score, 0.0, 10.0))
    v = float(np.clip(volume_momentum_score, 0.0, 10.0))
    c = float(np.clip(cycle_score, 0.0, 10.0))
    return float(np.clip(t * 0.4 + v * 0.3 + c * 0.3, 0.0, 10.0))


def ma_stack_score_0_10(close: float, ma20: float, ma50: float, ma100: float):
    """Reward simple trend stacking: price above multiple MAs."""
    stack = 0
    for ma in (ma20, ma50, ma100):
        if ma is not None and np.isfinite(ma) and ma > 0 and close > ma:
            stack += 1
    return float(stack / 3 * 10.0)


def detect_stock_phase(
    df: pd.DataFrame,
    vni_df: pd.DataFrame,
    breadth20_pct: float = 100.0,
    breadth50_pct: float = 100.0,
    prev_phase: str | None = None
):
    rs_score = relative_strength_score(df, vni_df)
    va_score = volume_accumulation_score(df)

    # Attempt cycle-based phase detection using past data only
    try:
        window = max(int(getattr(settings, 'lookback_min', 150)), 120)
        cycle = cycle_service.compute_cycle_for_series(df['close'], window=window, min_points=60)
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

    # If cycle is too weak, avoid forcing a directional phase.
    amp_threshold = 0.2
    if np.isfinite(amplitude) and amplitude < amp_threshold:
        return {'phase': 'SIDEWAYS_NO_PHASE', 'rs_score': rs_score, 'va_score': va_score}

    # Compute a simple amplitude-to-volatility ratio to distinguish strong cycles
    last_price = float(df['close'].iloc[-1])
    vol_price = float(df['close'].pct_change().dropna().tail(20).std() * last_price) if len(df) >= 5 else 0.0
    amp_rel = amplitude / vol_price if vol_price and np.isfinite(amplitude) else 0.0

    regime = cycle_service.map_phase_to_regime(
        phase,
        amp_rel=amp_rel,
        rs_score=rs_score,
        va_score=va_score,
        breadth20_pct=breadth20_pct,
        breadth50_pct=breadth50_pct
    )

    # Hysteresis around phase boundaries to reduce one-bar flip noise.
    if prev_phase and regime != prev_phase:
        deg = float(np.degrees(phase))
        deg = ((deg + 180.0) % 360.0) - 180.0
        boundary_dist = min(abs(deg + 90.0), abs(deg), abs(deg - 90.0), abs(abs(deg) - 180.0))
        directional = {'ACCUMULATION_WEAK', 'ACCUMULATION_STRONG', 'MARKUP', 'DISTRIBUTION', 'MARKDOWN'}
        if prev_phase in directional and regime in directional and boundary_dist <= 12.0:
            regime = prev_phase

    # Confirm MARKUP only when market breadth is supportive.
    if regime == 'MARKUP' and breadth50_pct <= 60.0:
        regime = 'SIDEWAYS_NO_PHASE'

    # Trend override: bullish long-term trend cannot be classified as MARKDOWN.
    ma50 = float(df['ma50'].iloc[-1]) if 'ma50' in df.columns and pd.notna(df['ma50'].iloc[-1]) else np.nan
    ma200 = float(df['ma200'].iloc[-1]) if 'ma200' in df.columns and pd.notna(df['ma200'].iloc[-1]) else np.nan
    if regime == 'MARKDOWN' and np.isfinite(ma50) and np.isfinite(ma200) and ma50 > ma200:
        regime = 'SIDEWAYS_NO_PHASE'

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

    setup_status = score_data.get('setup_status')
    if setup_status in ('INVALID_PHASE', 'LOW_LIQUIDITY', 'DATA_ERROR', 'RR_REJECTED', 'NO_TRADE_PLAN'):
        for key in ('score', 'confidence'):
            value = score_data.get(key)
            if value is None or not np.isfinite(value):
                issues.append(f'invalid_{key}')
            elif isinstance(value, (int, float)) and value < 0:
                issues.append(f'negative_{key}')
        if issues:
            return False, ','.join(issues)
        return True, ''

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
    market_confidence: float | None = None,
    breadth20_pct: float = 100.0,
    breadth50_pct: float = 100.0,
    phase_context: dict | None = None,
    sector_context: dict | None = None
):
    """Scoring V3: trend + volume + RS dominant; cycle is contextual."""
    last = df.iloc[-1]
    close = float(last['close'])
    if close <= 0:
        logger.warning(f"{symbol}: non-positive close ({close}), skipping signal")
        return None

    if phase_context is None:
        phase_context = detect_stock_phase(
            df, vni_df, breadth20_pct=breadth20_pct, breadth50_pct=breadth50_pct
        )
    regime = phase_context['phase']
    market_alignment = signal_service.resolve_market_alignment(market_regime, regime)

    rs_0_10 = float(np.clip(rs_score_0_10(df, vni_df), 0.0, 10.0))
    liquidity_score = float(np.clip(last.get('liquidity_score', 5.0), 0.0, 10.0)) if pd.notna(last.get('liquidity_score')) else 5.0
    ma20 = float(last.get('ma20', np.nan))
    ma50 = float(last.get('ma50', np.nan))
    ma100 = float(last.get('ma100', np.nan))
    ma200 = float(last.get('ma200', np.nan))

    stack = sum(1 for ma in (ma20, ma50, ma100, ma200) if np.isfinite(ma) and ma > 0 and close > ma)
    stack_score = float(stack / 4.0 * 10.0)
    slopes = [last.get('ma20_slope'), last.get('ma50_slope'), last.get('ma100_slope')]
    slope_pos = sum(1 for v in slopes if pd.notna(v) and float(v) > 0)
    slope_score = float(slope_pos / max(len(slopes), 1) * 10.0)
    trend_score = float(np.clip(stack_score * 0.7 + slope_score * 0.3, 0.0, 10.0))

    volume_score_0_10 = float(np.clip(volume_momentum_score_0_10(df), 0.0, 10.0))
    cycle_score_0_10 = 5.0
    if 'cycle_phase' in df.columns and pd.notna(df['cycle_phase'].iloc[-1]):
        cp = float(df['cycle_phase'].iloc[-1])
        cycle_score_0_10 = float(np.clip((np.cos(cp) + 1.0) / 2.0 * 10.0, 0.0, 10.0))

    sector_score = 0.0
    if sector_context:
        sector_score = float(np.clip(sector_context.get('sector_score', 0.0), 0.0, 10.0))
    trend_score *= (0.95 + 0.10 * (sector_score / 10.0))
    trend_score = float(np.clip(trend_score, 0.0, 10.0))

    # Component-level market regime adjustment.
    if market_regime == 'MARKDOWN':
        trend_score *= 0.7
        volume_score_0_10 *= 0.6
    elif market_regime == 'DISTRIBUTION':
        trend_score *= 0.85
        volume_score_0_10 *= 0.8
    elif market_regime == 'MARKUP':
        trend_score *= 1.1
    trend_score = float(np.clip(trend_score, 0.0, 10.0))
    volume_score_0_10 = float(np.clip(volume_score_0_10, 0.0, 10.0))

    # Final score weights: Trend 40, Volume 25, RS 20, Cycle 10, Liquidity 5.
    final_0_10 = (
        trend_score * 0.40 +
        volume_score_0_10 * 0.25 +
        rs_0_10 * 0.20 +
        cycle_score_0_10 * 0.10 +
        liquidity_score * 0.05
    )
    score_value = float(np.clip(final_0_10 * 10.0, 0.0, 100.0))

    # Fake breakout filter.
    rolling_20_high_prev = df['high'].rolling(20).max().shift(1).iloc[-1]
    if not np.isfinite(rolling_20_high_prev) or rolling_20_high_prev <= 0:
        rolling_20_high_prev = close
    recent = df.tail(2)
    vol_spike_days = int((recent['volume_ratio'] > 1.5).sum()) if len(recent) == 2 else 0
    breakout_condition_met = close >= float(rolling_20_high_prev)
    near_breakout = close < float(rolling_20_high_prev) * 1.01
    weak_breakout = bool(breakout_condition_met and near_breakout and vol_spike_days == 1)
    if weak_breakout:
        score_value *= 0.70
    score_value = float(np.clip(score_value, 0.0, 100.0))

    confidence = score_value
    avg_value_20 = float(last.get('avg_value_20')) if pd.notna(last.get('avg_value_20')) else np.nan
    low_liquidity = bool(np.isfinite(avg_value_20) and avg_value_20 < settings.liquidity_min_avg_value)

    signal_ctx = signal_service.classify_trade_signal(
        score=score_value,
        stock_phase=regime,
        rs_0_10=rs_0_10,
        trend_score=trend_score,
        low_liquidity=low_liquidity,
    )
    trade_signal = signal_service.apply_market_gate(
        signal_ctx['trade_signal'], market_regime, market_confidence, regime, trend_score, rs_0_10
    )
    setup_status = signal_ctx['setup_status']
    if setup_status in ('BUY', 'SETUP', 'WATCH', 'AVOID'):
        setup_status = trade_signal
    if weak_breakout and trade_signal in ('BUY', 'SETUP'):
        trade_signal = 'WATCH'
        setup_status = 'WEAK_BREAKOUT'

    action = 'BUY' if trade_signal == 'BUY' else ('WATCH' if trade_signal in ('SETUP', 'WATCH') else 'AVOID')
    if trade_signal == 'AVOID':
        setup_status = 'NO_TRADE_PLAN'

    phase_invalid = signal_ctx.get('phase_invalid', False)
    if phase_invalid or low_liquidity:
        trade_plan = {
            'entry': close,
            'stop': None,
            'target': None,
            'rr': None,
            'take_profit': None,
            'buy_zone_low': None,
            'buy_zone_high': None,
            'tp_zone': None,
            'stop_loss': None,
            'risk_reward': None,
            'plan_status': 'NO_TRADE_PLAN'
        }
    else:
        trade_plan = trade_service.generate_trade_plan(df, trade_signal=trade_signal, min_rr=1.3)
        if trade_plan.get('plan_status') == 'RR_REJECTED':
            trade_signal = 'WATCH'
            action = 'WATCH'
            setup_status = 'RR_REJECTED'
        elif trade_plan.get('plan_status') == 'NO_TRADE_PLAN':
            setup_status = 'NO_TRADE_PLAN'

    rr = trade_plan.get('rr')
    setup_quality = float(score_value * rr) if rr is not None and np.isfinite(rr) else 0.0
    setup_tier = signal_ctx.get('setup_tier')

    logger.debug(
        "%s score_v3 trend=%.1f vol=%.1f rs=%.1f cyc=%.1f liq=%.1f sector=%.1f final=%.1f signal=%s",
        symbol, trend_score, volume_score_0_10, rs_0_10, cycle_score_0_10, liquidity_score, sector_score, score_value, trade_signal
    )

    return {
        'regime': regime,
        'phase': regime,
        'action': action,
        'trade_signal': trade_signal,
        'setup_status': setup_status,
        'market_alignment': market_alignment,
        'model_version': MODEL_VERSION,
        'setup_tier': setup_tier,
        'sector_score': sector_score,
        'confidence': confidence,
        'score': score_value,
        'setup_quality': setup_quality,
        'entry': trade_plan.get('entry'),
        'stop': trade_plan.get('stop'),
        'target': trade_plan.get('target'),
        'take_profit': trade_plan.get('take_profit'),
        'rr': trade_plan.get('rr'),
        'buy_zone': None,
        'buy_zone_low': trade_plan.get('buy_zone_low'),
        'buy_zone_high': trade_plan.get('buy_zone_high'),
        'tp_zone': trade_plan.get('tp_zone'),
        'stop_loss': trade_plan.get('stop_loss'),
        'risk_reward': trade_plan.get('risk_reward')
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
        exists.trade_signal = score_data.get('trade_signal')
        exists.sector_score = score_data.get('sector_score')
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
            trade_signal=score_data.get('trade_signal'),
            sector_score=score_data.get('sector_score'),
            model_version=score_data.get('model_version'),
            setup_tier=score_data.get('setup_tier')
        ))
    session.commit()
