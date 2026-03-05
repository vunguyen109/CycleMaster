import numpy as np
import pandas as pd
from scipy.signal import hilbert
from numpy.lib.stride_tricks import sliding_window_view


def _safe_to_1d_array(series: pd.Series) -> np.ndarray:
    return np.asarray(series.astype(float).values)


def _smooth_phase_sma3(phase_arr: np.ndarray) -> np.ndarray:
    """Causal 3-bar smoothing for phase to reduce right-edge flicker."""
    phase = np.asarray(phase_arr, dtype=float).copy()
    valid = np.isfinite(phase)
    if not np.any(valid):
        return phase
    sin_s = pd.Series(np.sin(phase))
    cos_s = pd.Series(np.cos(phase))
    sin_sm = sin_s.rolling(window=3, min_periods=1).mean().to_numpy()
    cos_sm = cos_s.rolling(window=3, min_periods=1).mean().to_numpy()
    smoothed = np.arctan2(sin_sm, cos_sm)
    smoothed[~valid] = np.nan
    return smoothed


def compute_cycle_dataframe(
    prices: pd.Series,
    window: int = 120,
    detrend_ma: int = 50,
    min_periods: int = 30,
    compute_dominant_period: bool = False,
):
    if not isinstance(prices, pd.Series):
        prices = pd.Series(prices)

    n = len(prices)
    idx = prices.index

    phase_out = np.full(n, np.nan, dtype=float)
    amp_out = np.full(n, np.nan, dtype=float)
    pos_out = np.full(n, np.nan, dtype=float)
    dom_out = np.full(n, np.nan, dtype=float) if compute_dominant_period else None

    if n < min_periods or window < 3:
        cols = {
            'cycle_phase': phase_out,
            'cycle_position': pos_out,
            'cycle_amplitude': amp_out,
        }
        if compute_dominant_period:
            cols['dominant_cycle_period'] = dom_out
        return pd.DataFrame(cols, index=idx)

    x = _safe_to_1d_array(prices)

    # Detrend using past moving average (no lookahead)
    s = pd.Series(x)
    trend = s.rolling(window=detrend_ma, min_periods=1).mean().to_numpy()
    detr = x - trend

    win = window if n >= window else n

    # Build sliding windows of detrended data; each row ends at time t (no future)
    try:
        windows = sliding_window_view(detr, window_shape=win)
    except Exception:
        windows = np.vstack([
            detr[max(0, i - win + 1): i + 1]
            if i - win + 1 >= 0
            else np.concatenate((np.full(win - (i + 1), np.nan), detr[: i + 1]))
            for i in range(n)
        ])
        if windows.ndim == 2 and windows.shape[0] >= win:
            windows = windows[win - 1:]

    m = windows.shape[0]
    if m <= 0:
        cols = {
            'cycle_phase': phase_out,
            'cycle_position': pos_out,
            'cycle_amplitude': amp_out,
        }
        if compute_dominant_period:
            cols['dominant_cycle_period'] = dom_out
        return pd.DataFrame(cols, index=idx)

    valid = ~np.isnan(windows).any(axis=1)

    win_func = np.hanning(win).astype(float)
    windowed = windows * win_func[None, :]

    try:
        analytic = hilbert(windowed, axis=1)
    except Exception:
        cols = {
            'cycle_phase': phase_out,
            'cycle_position': pos_out,
            'cycle_amplitude': amp_out,
        }
        if compute_dominant_period:
            cols['dominant_cycle_period'] = dom_out
        return pd.DataFrame(cols, index=idx)

    inst_phase = np.angle(analytic[:, -1])
    inst_amp = np.abs(analytic[:, -1])

    out_indices = np.arange(win - 1, win - 1 + m)
    phase_out[out_indices] = np.where(valid, inst_phase, np.nan)
    amp_out[out_indices] = np.where(valid, inst_amp, np.nan)
    phase_out = _smooth_phase_sma3(phase_out)

    pos = (phase_out + np.pi) / (2 * np.pi)
    pos_out[:] = pos

    if compute_dominant_period:
        try:
            fft = np.fft.rfft(windowed, axis=1)
            power = np.abs(fft) ** 2
            freqs = np.fft.rfftfreq(win, d=1.0)
            freq_mask = freqs > 0
            freqs = freqs[freq_mask]
            power = power[:, freq_mask]

            min_period = 3.0
            max_period = max(3.0, float(win))
            search_mask = (freqs >= 1.0 / max_period) & (freqs <= 1.0 / min_period)
            if not np.any(search_mask):
                dom = np.full(m, np.nan)
            else:
                search_power = power[:, search_mask]
                search_power[~valid, :] = -np.inf
                idx_max = np.nanargmax(search_power, axis=1)
                freqs_sel = freqs[search_mask]
                dom = np.where(valid, 1.0 / freqs_sel[idx_max], np.nan)
        except Exception:
            dom = np.full(m, np.nan)
        dom_out[out_indices] = dom

    cols = {
        'cycle_phase': phase_out,
        'cycle_position': pos_out,
        'cycle_amplitude': amp_out,
    }
    if compute_dominant_period:
        cols['dominant_cycle_period'] = dom_out

    return pd.DataFrame(cols, index=idx)


def classify_cycle_phase(phase: float | np.ndarray) -> np.ndarray:
    arr = np.asarray(phase)
    scalar = arr.shape == ()
    deg = np.degrees(arr)
    out = np.full(deg.shape, 'bottom', dtype=object)

    mask_nan = np.isnan(deg)
    bottom_mask = (deg > -180.0) & (deg <= -90.0)
    rising_mask = (deg > -90.0) & (deg <= 0.0)
    top_mask = (deg > 0.0) & (deg <= 90.0)
    falling_mask = (deg > 90.0) & (deg <= 180.0)

    out[bottom_mask] = 'bottom'
    out[rising_mask] = 'rising'
    out[top_mask] = 'top'
    out[falling_mask] = 'falling'
    out[mask_nan] = None

    if scalar:
        return out.item()
    return out


def map_phase_to_regime(
    phase_rad: float,
    amp_rel: float = 0.0,
    rs_score: float = 0.0,
    va_score: float = 0.0,
    breadth20_pct: float = 100.0,
    breadth50_pct: float = 100.0
) -> str:
    deg = float(np.degrees(phase_rad))
    # Normalize and snap boundary values to avoid floating-point flicker:
    # e.g. -90.00000000000004 should be treated as -90.0.
    deg = ((deg + 180.0) % 360.0) - 180.0
    eps = 1e-3
    if abs(deg + 90.0) <= eps:
        deg = -90.0
    elif abs(deg) <= eps:
        deg = 0.0
    elif abs(deg - 90.0) <= eps:
        deg = 90.0
    elif abs(abs(deg) - 180.0) <= eps:
        deg = 180.0 if deg >= 0 else -180.0

    if -90.0 <= deg < 0.0:
        if amp_rel > 0.8 and rs_score > 0 and va_score > 0 and breadth20_pct >= 40 and breadth50_pct >= 30:
            return 'ACCUMULATION_STRONG'
        return 'ACCUMULATION_WEAK'
    if 0.0 <= deg < 90.0:
        return 'MARKUP'
    if 90.0 <= deg <= 180.0:
        return 'DISTRIBUTION'
    return 'MARKDOWN'


def compute_cycle_for_series(series: pd.Series, window: int = 120, detrend_ma: int = 50, min_points: int = 60, compute_dominant_period: bool = False):
    df = compute_cycle_dataframe(series, window=window, detrend_ma=detrend_ma, min_periods=min_points, compute_dominant_period=compute_dominant_period)
    if df.empty:
        return {'cycle_phase': float('nan'), 'cycle_amplitude': float('nan'), 'dominant_period': float('nan')}
    last = df.iloc[-1]
    return {
        'cycle_phase': float(last['cycle_phase']) if pd.notna(last['cycle_phase']) else float('nan'),
        'cycle_amplitude': float(last['cycle_amplitude']) if pd.notna(last['cycle_amplitude']) else float('nan'),
        'dominant_period': float(last['dominant_cycle_period']) if ('dominant_cycle_period' in df.columns and pd.notna(last.get('dominant_cycle_period'))) else float('nan')
    }
