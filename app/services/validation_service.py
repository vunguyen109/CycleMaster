import pandas as pd


REQUIRED_OHLCV_COLUMNS = ['open', 'high', 'low', 'close', 'volume']


def validate_ohlcv(df: pd.DataFrame, min_sessions: int = 120):
    if df is None or df.empty:
        return False, 'empty'
    missing_cols = [col for col in REQUIRED_OHLCV_COLUMNS if col not in df.columns]
    if missing_cols:
        return False, f'missing_columns:{",".join(missing_cols)}'
    if df[REQUIRED_OHLCV_COLUMNS].isna().any().any():
        return False, 'missing_ohlcv'
    if (df['close'] <= 0).any():
        return False, 'non_positive_close'
    if (df['volume'] <= 0).any():
        return False, 'non_positive_volume'
    if len(df) < min_sessions:
        return False, f'insufficient_sessions:{len(df)}'
    return True, ''
