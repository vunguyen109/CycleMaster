import logging
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from app.models import models


logger = logging.getLogger(__name__)


class MockDataProvider:
    def __init__(self):
        self.data_dir = Path('data')
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.seed_file = self.data_dir / 'seed_ohlcv.csv'
        self.vnindex_file = self.data_dir / 'seed_vnindex.csv'

    def _generate_mock_series(self, symbol: str, days: int = 250):
        rng = np.random.default_rng(abs(hash(symbol)) % (2**32))
        dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=days, freq='B')
        price = 20 + rng.normal(0, 0.4, size=days).cumsum() + rng.uniform(0, 5)
        price = np.maximum(price, 1)
        high = price + rng.uniform(0.1, 0.8, size=days)
        low = price - rng.uniform(0.1, 0.8, size=days)
        open_ = price + rng.normal(0, 0.2, size=days)
        close = price + rng.normal(0, 0.2, size=days)
        volume = rng.integers(50000, 2000000, size=days)
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

    def load_or_create(self, symbols):
        if self.seed_file.exists():
            df = pd.read_csv(self.seed_file, parse_dates=['date'])
        else:
            frames = [self._generate_mock_series(sym) for sym in symbols]
            df = pd.concat(frames, ignore_index=True)
            df.to_csv(self.seed_file, index=False)
        return df

    def load_vnindex(self):
        if self.vnindex_file.exists():
            df = pd.read_csv(self.vnindex_file, parse_dates=['date'])
        else:
            df = self._generate_mock_series('VNINDEX')
            df.to_csv(self.vnindex_file, index=False)
        return df


def get_symbols(session: Session):
    symbols = [s.symbol for s in session.query(models.Stock).all()]
    if not symbols:
        symbols = ['HPG', 'VNM', 'VCB', 'FPT', 'SSI', 'MWG', 'VIC', 'GMD', 'PNJ', 'ACB']
        for sym in symbols:
            session.add(models.Stock(symbol=sym, sector=''))
        session.commit()
    return symbols


def store_ohlcv(session: Session, df: pd.DataFrame):
    for _, row in df.iterrows():
        exists = session.query(models.OHLCV).filter_by(symbol=row['symbol'], date=row['date'].date()).first()
        if exists:
            continue
        session.add(models.OHLCV(
            symbol=row['symbol'],
            date=row['date'].date(),
            open=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=float(row['volume'])
        ))
    session.commit()


def fetch_ohlcv(session: Session, symbols):
    provider = MockDataProvider()
    df = provider.load_or_create(symbols)
    store_ohlcv(session, df)
    return df


def fetch_vnindex(session: Session):
    provider = MockDataProvider()
    df = provider.load_vnindex()
    store_ohlcv(session, df)
    return df
