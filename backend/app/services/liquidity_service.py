import pandas as pd


def compute_liquidity_metrics(df: pd.DataFrame) -> dict:
    avg_volume_20 = df['volume'].rolling(20).mean().iloc[-1]
    avg_value_20 = (df['close'] * 1000 * df['volume']).rolling(20).mean().iloc[-1]
    liquidity_score = liquidity_score_from_avg_value(avg_value_20)
    return {
        'avg_volume_20': float(avg_volume_20) if pd.notna(avg_volume_20) else float('nan'),
        'avg_value_20': float(avg_value_20) if pd.notna(avg_value_20) else float('nan'),
        'liquidity_score': liquidity_score
    }


def liquidity_score_from_avg_value(avg_value_20: float) -> float:
    if avg_value_20 is None or pd.isna(avg_value_20):
        return 0.0
    if avg_value_20 > 200_000_000_000:
        return 10.0
    if avg_value_20 >= 100_000_000_000:
        return 8.0
    if avg_value_20 >= 50_000_000_000:
        return 6.0
    if avg_value_20 >= 20_000_000_000:
        return 4.0
    return 0.0


def rank_liquidity(metrics_by_symbol: dict) -> dict:
    if not metrics_by_symbol:
        return metrics_by_symbol
    series = pd.Series({sym: data.get('avg_value_20') for sym, data in metrics_by_symbol.items()})
    ranks = series.rank(pct=True)
    for sym, data in metrics_by_symbol.items():
        pct = ranks.get(sym)
        data['liquidity_percentile_rank'] = float(pct * 100) if pd.notna(pct) else 0.0
    return metrics_by_symbol


def passes_liquidity_filter(metrics: dict, min_avg_volume: float, min_avg_value: float) -> bool:
    avg_vol = metrics.get('avg_volume_20')
    avg_val = metrics.get('avg_value_20')
    if avg_vol is None or avg_val is None:
        return False
    if pd.isna(avg_vol) or pd.isna(avg_val):
        return False
    return avg_vol >= min_avg_volume and avg_val >= min_avg_value
