import numpy as np
import pandas as pd


def _safe_float(value, default=np.nan) -> float:
    try:
        if value is None:
            return float(default)
        out = float(value)
        return out if np.isfinite(out) else float(default)
    except Exception:
        return float(default)


def _compute_atr_fallback(df: pd.DataFrame) -> float:
    last = df.iloc[-1]
    atr_val = _safe_float(last.get('atr'))
    if np.isfinite(atr_val) and atr_val > 0:
        return atr_val
    ma20 = _safe_float(last.get('ma20'))
    if np.isfinite(ma20) and ma20 > 0:
        return ma20 * 0.03
    high20 = _safe_float(df['high'].rolling(20).max().iloc[-1], default=0.0)
    low20 = _safe_float(df['low'].rolling(20).min().iloc[-1], default=0.0)
    if high20 > low20 > 0:
        return max((high20 - low20) / 3.5, 1e-6)
    close = _safe_float(last.get('close'), default=1.0)
    return max(close * 0.03, 1e-6)


def generate_trade_plan(df: pd.DataFrame, trade_signal: str, min_rr: float = 1.3) -> dict:
    """Entry = breakout_level OR pullback_to_ma20. Stop/target use ATR system."""
    last = df.iloc[-1]
    close = _safe_float(last.get('close'))
    if trade_signal not in ('BUY', 'SETUP', 'WATCH') or not np.isfinite(close) or close <= 0:
        return {
            'entry': close if np.isfinite(close) and close > 0 else None,
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

    atr_val = max(_compute_atr_fallback(df), 1e-6)
    breakout_level = _safe_float(df['high'].rolling(20).max().shift(1).iloc[-1], default=close)
    ma20 = _safe_float(last.get('ma20'), default=close)

    breakout_confirmed = np.isfinite(breakout_level) and close >= breakout_level * 1.001
    pullback_to_ma20 = np.isfinite(ma20) and abs(close / ma20 - 1.0) <= 0.01

    if breakout_confirmed:
        entry = max(close, breakout_level)
    elif pullback_to_ma20:
        entry = ma20
    else:
        entry = close

    stop = entry - 1.5 * atr_val
    target = entry + 3.0 * atr_val
    if stop <= 0 or target <= 0:
        return {
            'entry': entry,
            'stop': None,
            'target': None,
            'rr': None,
            'take_profit': None,
            'buy_zone_low': None,
            'buy_zone_high': None,
            'tp_zone': None,
            'stop_loss': None,
            'risk_reward': None,
            'plan_status': 'DATA_ERROR'
        }

    rr = (target - entry) / max(entry - stop, 1e-6)
    if not np.isfinite(rr) or rr < min_rr:
        return {
            'entry': entry,
            'stop': None,
            'target': None,
            'rr': None,
            'take_profit': None,
            'buy_zone_low': None,
            'buy_zone_high': None,
            'tp_zone': None,
            'stop_loss': None,
            'risk_reward': None,
            'plan_status': 'RR_REJECTED'
        }

    return {
        'entry': entry,
        'stop': stop,
        'target': target,
        'rr': rr,
        'take_profit': target,
        'buy_zone_low': None,
        'buy_zone_high': None,
        'tp_zone': None,
        'stop_loss': stop,
        'risk_reward': rr,
        'plan_status': 'VALID'
    }
