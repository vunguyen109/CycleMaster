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
    if setup_status == 'INVALID_PHASE':
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
    breadth20_pct: float = 100.0,
    breadth50_pct: float = 100.0,
    phase_context: dict | None = None,
    sector_context: dict | None = None
):
    """Scoring V2 with strict 0-100 normalization.

    FinalScore_0_10 = TechnicalScore*0.6 + RSScore*0.2 + LiquidityScore*0.2
    TechnicalScore = Trend*0.4 + VolumeMomentum*0.3 + Cycle*0.3
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

    # V2 components (all 0..10 scale)
    rs_0_10 = float(np.clip(rs_score_0_10(df, vni_df), 0.0, 10.0))
    liquidity_score = df['liquidity_score'].iloc[-1] if 'liquidity_score' in df.columns else 5.0
    if not np.isfinite(liquidity_score):
        liquidity_score = 5.0
    liquidity_score = float(np.clip(liquidity_score, 0.0, 10.0))

    trend_score = ma_stack_score_0_10(
        close,
        float(last.get('ma20', np.nan)),
        float(last.get('ma50', np.nan)),
        float(last.get('ma100', np.nan))
    )
    volume_score_0_10 = volume_momentum_score_0_10(df)

    cycle_score_0_10 = 5.0
    if 'cycle_phase' in df.columns:
        try:
            cp = df['cycle_phase'].iloc[-1]
            if np.isfinite(cp):
                cycle_cos = float(np.cos(float(cp)))
                cycle_score_0_10 = float(np.clip((cycle_cos + 1.0) / 2.0 * 10.0, 0.0, 10.0))
        except Exception:
            cycle_score_0_10 = 5.0

    technical = technical_score_v2_0_10(trend_score, volume_score_0_10, cycle_score_0_10)

    # Exact V2 formula:
    # FinalScore_0_10 = Technical*0.6 + RS*0.2 + Liquidity*0.2
    final_score_0_10 = technical * 0.6 + rs_0_10 * 0.2 + liquidity_score * 0.2
    score_value = float(np.clip(final_score_0_10 * 10.0, 0.0, 100.0))

    # Market alignment multiplier (Section 1.2): only markdown applies penalty.
    if market_regime == 'MARKDOWN':
        # Preserve early leaders in weak markets.
        if not (rs_0_10 > 8.0 and trend_score >= 8.0):
            score_value *= 0.8

    # Fake breakout filter with ATH-volume exception (Section 3.1).
    recent = df.tail(2)
    vol_spike_days = int((recent['volume_ratio'] > 1.5).sum()) if len(recent) == 2 else 0
    breakout_level = float(rolling_20_high)
    breakout_condition_met = bool(close >= breakout_level)
    near_breakout = bool(close < breakout_level * 1.01)
    high_52w = float(df['high'].rolling(252, min_periods=1).max().iloc[-1]) if len(df) > 0 else close
    avg_volume_20 = float(df['volume'].rolling(20).mean().iloc[-1]) if len(df) > 0 else 0.0
    last_volume = float(last.get('volume')) if pd.notna(last.get('volume')) else 0.0
    ath_exception = bool(
        np.isfinite(high_52w) and close >= high_52w and avg_volume_20 > 0 and last_volume > 2.5 * avg_volume_20
    )
    if breakout_condition_met and near_breakout and vol_spike_days == 1 and not ath_exception:
        score_value *= 0.70

    score_value = float(np.clip(score_value, 0.0, 100.0))
    confidence = score_value

    market_alignment = 'NEUTRAL'
    if market_regime in ('MARKUP', 'ACCUMULATION', 'ACCUMULATION_STRONG', 'ACCUMULATION_WEAK'):
        market_alignment = 'ALIGNED'
    elif market_regime in ('DISTRIBUTION', 'MARKDOWN'):
        market_alignment = 'MISALIGNED'

    logger.debug(
        "%s score_breakdown tech_v2=%.1f trend=%.1f vol=%.1f cyc=%.1f rs=%.1f liq=%.1f final=%.1f",
        symbol, technical, trend_score, volume_score_0_10, cycle_score_0_10, rs_0_10, liquidity_score, score_value
    )

    phase_invalid = regime in ('DISTRIBUTION', 'MARKDOWN')

    # Dynamic action thresholds to keep buy signals selective in weak regimes.
    buy_threshold = 70.0
    watch_threshold = 55.0
    if regime == 'DISTRIBUTION':
        buy_threshold = 999.0
        watch_threshold = 60.0
    elif regime == 'MARKDOWN':
        buy_threshold = 999.0
        watch_threshold = 58.0

    if market_regime == 'MARKDOWN':
        buy_threshold += 4.0
        watch_threshold += 2.0
    elif market_regime == 'DISTRIBUTION':
        buy_threshold += 2.0
        watch_threshold += 1.0

    vol_ratio_last = float(last['volume_ratio']) if pd.notna(last.get('volume_ratio')) else 0.0
    ma50_last = float(last['ma50']) if pd.notna(last.get('ma50')) else np.nan
    above_ma50 = bool(np.isfinite(ma50_last) and ma50_last > 0 and close > ma50_last)

    # Quality gates for bullish actions.
    high_quality = trend_score >= 6.7 and rs_0_10 >= 5.0 and vol_ratio_last >= 1.0
    very_high_quality = trend_score >= 10.0 and rs_0_10 >= 5.5 and vol_ratio_last >= 1.1 and above_ma50

    if score_value >= buy_threshold:
        action = 'BUY'
    elif score_value >= watch_threshold:
        action = 'WATCH'
    else:
        action = 'AVOID'

    # Prevent low-quality BUY in bearish market backdrop.
    if action == 'BUY' and not high_quality:
        action = 'WATCH'
    if action == 'WATCH' and market_regime == 'MARKDOWN' and trend_score < 3.4 and rs_0_10 < 5.0:
        action = 'AVOID'

    # In bearish market, keep an early-watch lane for strong trend stacks.
    if (
        action == 'AVOID'
        and market_regime == 'MARKDOWN'
        and trend_score >= 10.0
        and vol_ratio_last >= 1.2
        and rs_0_10 >= 4.5
        and score_value >= 50.0
    ):
        action = 'WATCH'
    if phase_invalid:
        if rs_0_10 > 8.0 and trend_score >= 8.0:
            action = 'WATCH'
        else:
            action = 'AVOID'
        setup_status = 'INVALID_PHASE'
    else:
        setup_status = action  # keep legacy key for database compatibility

    # Phase gating: no trade plan for structurally weak phases.
    if phase_invalid:
        return {
            'regime': regime,
            'phase': regime,
            'action': action,
            'setup_status': setup_status,
            'market_alignment': market_alignment,
            'model_version': 'v6',
            'setup_tier': None,
            'confidence': confidence,
            'score': score_value,
            'setup_quality': 0.0,
            'entry': close,
            'stop': None,
            'target': None,
            'take_profit': None,
            'rr': None,
            'buy_zone': None,
            'buy_zone_low': None,
            'buy_zone_high': None,
            'tp_zone': None,
            'stop_loss': None,
            'risk_reward': None
        }

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
        'model_version': 'v6',
        'setup_tier': setup_tier,
        'confidence': confidence,
        'score': score_value,
        'setup_quality': setup_quality,
        'entry': entry,
        'stop': stop,
        'target': target,
        'take_profit': target,
        'rr': rr,
        'buy_zone': None,
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
