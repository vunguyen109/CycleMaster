import numpy as np
import pandas as pd


def _clip01(value: float) -> float:
    if value is None or not np.isfinite(value):
        return 0.0
    return float(np.clip(value, 0.0, 10.0))


def _linear_to_0_10(value: float, low: float, high: float) -> float:
    if value is None or not np.isfinite(value):
        return 0.0
    if value <= low:
        return 0.0
    if value >= high:
        return 10.0
    return float((value - low) / (high - low) * 10.0)


def compute_sector_strength(feature_cache: dict[str, pd.DataFrame], sector_map: dict[str, str], vni_df: pd.DataFrame) -> dict[str, dict]:
    """Compute sector rotation strength and normalize to sector_score 0..10."""
    sector_bucket: dict[str, dict] = {}
    vni_ret20 = float(vni_df['close'].pct_change(20).iloc[-1]) if len(vni_df) > 25 else 0.0

    for symbol, df in feature_cache.items():
        if df is None or df.empty:
            continue
        sector = (sector_map.get(symbol) or 'UNKNOWN').strip() or 'UNKNOWN'
        last = df.iloc[-1]
        ret20 = float(df['close'].pct_change(20).iloc[-1]) if len(df) > 25 else 0.0
        vol_ma5 = float(df['volume'].rolling(5).mean().iloc[-1]) if len(df) >= 5 else np.nan
        vol_ma20 = float(df['volume'].rolling(20).mean().iloc[-1]) if len(df) >= 20 else np.nan
        vol_change = ((vol_ma5 / vol_ma20) - 1.0) if np.isfinite(vol_ma5) and np.isfinite(vol_ma20) and vol_ma20 > 0 else 0.0
        ma20 = float(last.get('ma20')) if pd.notna(last.get('ma20')) else np.nan
        breadth_hit = 1 if np.isfinite(ma20) and float(last['close']) > ma20 else 0

        bucket = sector_bucket.setdefault(sector, {'ret20': [], 'vol_change': [], 'breadth': []})
        bucket['ret20'].append(ret20)
        bucket['vol_change'].append(vol_change)
        bucket['breadth'].append(breadth_hit)

    sector_metrics: dict[str, dict] = {}
    for sector, bucket in sector_bucket.items():
        ret20_avg = float(np.mean(bucket['ret20'])) if bucket['ret20'] else 0.0
        vol_change_avg = float(np.mean(bucket['vol_change'])) if bucket['vol_change'] else 0.0
        breadth_pct = float(np.mean(bucket['breadth']) * 100.0) if bucket['breadth'] else 0.0
        rs_vs_index = ret20_avg - vni_ret20

        # SectorScore = return (45%) + relative strength (35%) + volume expansion (20%)
        return_score = _linear_to_0_10(ret20_avg, -0.05, 0.20)
        rs_score = _linear_to_0_10(rs_vs_index, -0.05, 0.15)
        vol_score = _linear_to_0_10(vol_change_avg, -0.20, 0.60)
        sector_score = _clip01(return_score * 0.45 + rs_score * 0.35 + vol_score * 0.20)

        sector_metrics[sector] = {
            'sector_return_20d': ret20_avg,
            'sector_volume_change': vol_change_avg,
            'sector_relative_strength': rs_vs_index,
            'sector_breadth_pct': breadth_pct,
            'sector_score': sector_score
        }

    return sector_metrics


def get_symbol_sector_context(symbol: str, sector_map: dict[str, str], sector_metrics: dict[str, dict]) -> dict:
    sector = (sector_map.get(symbol) or 'UNKNOWN').strip() or 'UNKNOWN'
    return sector_metrics.get(sector, {
        'sector_return_20d': 0.0,
        'sector_volume_change': 0.0,
        'sector_relative_strength': 0.0,
        'sector_breadth_pct': 0.0,
        'sector_score': 0.0
    })
