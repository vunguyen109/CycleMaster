import pandas as pd
import numpy as np
from pathlib import Path


def generate_series(symbol: str, days: int = 260):
    rng = np.random.default_rng(abs(hash(symbol)) % (2**32))
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=days, freq='B')
    price = 15 + rng.normal(0, 0.5, size=days).cumsum() + rng.uniform(0, 8)
    price = np.maximum(price, 1)
    high = price + rng.uniform(0.1, 1.2, size=days)
    low = price - rng.uniform(0.1, 1.2, size=days)
    open_ = price + rng.normal(0, 0.2, size=days)
    close = price + rng.normal(0, 0.2, size=days)
    volume = rng.integers(80000, 2500000, size=days)
    df = pd.DataFrame({
        'date': dates,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })
    df['symbol'] = symbol
    return df


def main():
    data_dir = Path('data')
    data_dir.mkdir(parents=True, exist_ok=True)
    symbols = ['HPG', 'VNM', 'VCB', 'FPT', 'SSI', 'MWG', 'VIC', 'GMD', 'PNJ', 'ACB']
    frames = [generate_series(sym) for sym in symbols]
    all_df = pd.concat(frames, ignore_index=True)
    all_df.to_csv(data_dir / 'seed_ohlcv.csv', index=False)

    vnindex = generate_series('VNINDEX')
    vnindex.to_csv(data_dir / 'seed_vnindex.csv', index=False)


if __name__ == '__main__':
    main()
