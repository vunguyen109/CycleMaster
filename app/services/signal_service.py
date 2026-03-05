import numpy as np


def resolve_market_alignment(market_regime: str, stock_phase: str) -> str:
    bullish_market = {'MARKUP', 'ACCUMULATION', 'ACCUMULATION_STRONG', 'ACCUMULATION_WEAK'}
    bearish_market = {'DISTRIBUTION', 'MARKDOWN'}
    bullish_phase = {'MARKUP', 'ACCUMULATION_STRONG', 'ACCUMULATION_WEAK'}
    bearish_phase = {'DISTRIBUTION', 'MARKDOWN'}

    if market_regime in bullish_market:
        if stock_phase in bullish_phase:
            return 'ALIGNED'
        if stock_phase in bearish_phase:
            return 'MISALIGNED'
    elif market_regime in bearish_market:
        if stock_phase in bearish_phase:
            return 'ALIGNED'
        if stock_phase in bullish_phase:
            return 'MISALIGNED'
    return 'NEUTRAL'


def classify_trade_signal(
    score: float,
    stock_phase: str,
    rs_0_10: float,
    trend_score: float,
    low_liquidity: bool,
) -> dict:
    phase_invalid = stock_phase in ('DISTRIBUTION', 'MARKDOWN')
    positive_phase = stock_phase in ('ACCUMULATION_WEAK', 'ACCUMULATION_STRONG', 'MARKUP')
    trend_strong = trend_score >= 7.0
    trend_moderate = trend_score >= 5.0
    rs_positive = rs_0_10 >= 5.0

    if low_liquidity:
        return {'trade_signal': 'AVOID', 'setup_status': 'LOW_LIQUIDITY', 'setup_tier': None, 'phase_invalid': False}
    if phase_invalid:
        return {'trade_signal': 'AVOID', 'setup_status': 'INVALID_PHASE', 'setup_tier': None, 'phase_invalid': True}

    if score >= 75 and positive_phase and trend_strong and rs_positive:
        signal = 'BUY'
    elif score >= 65 and trend_moderate:
        signal = 'SETUP'
    elif score >= 55:
        signal = 'WATCH'
    else:
        signal = 'AVOID'

    if signal == 'BUY':
        tier = 'A'
    elif signal == 'SETUP':
        tier = 'B'
    elif signal == 'WATCH':
        tier = 'C'
    else:
        tier = None
    return {'trade_signal': signal, 'setup_status': signal, 'setup_tier': tier, 'phase_invalid': False}


def apply_market_gate(signal: str, market_regime: str, market_confidence: float | None, stock_phase: str, trend_score: float, rs_0_10: float) -> str:
    if signal not in ('BUY', 'SETUP'):
        return signal

    bearish = market_regime in ('DISTRIBUTION', 'MARKDOWN')
    conf = float(market_confidence) if market_confidence is not None and np.isfinite(market_confidence) else 0.0
    severe_bear = bearish and conf >= 60.0
    if not severe_bear:
        return signal

    # Only exceptional leaders can keep BUY/SETUP in severe bearish regimes.
    leader_phase = stock_phase in ('MARKUP', 'ACCUMULATION_STRONG')
    leader = leader_phase and trend_score >= 8.0 and rs_0_10 >= 8.0
    if leader:
        return signal
    return 'WATCH'
