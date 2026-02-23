import logging
from pathlib import Path
from typing import List
from datetime import datetime, timedelta
import os
import numpy as np
import pandas as pd
import requests
from sqlalchemy.orm import Session
from app.models import models
from app.utils.config import settings


logger = logging.getLogger(__name__)


class BaseProvider:
    def fetch_ohlcv(self, symbols: List[str]) -> pd.DataFrame:
        raise NotImplementedError

    def fetch_vnindex(self) -> pd.DataFrame:
        raise NotImplementedError


class MockDataProvider(BaseProvider):
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

    def fetch_ohlcv(self, symbols: List[str]) -> pd.DataFrame:
        return self.load_or_create(symbols)

    def fetch_vnindex(self) -> pd.DataFrame:
        return self.load_vnindex()


class VnstockProvider(BaseProvider):
    def __init__(self):
        if settings.vnstock_api_key:
            os.environ['VNSTOCK_API_KEY'] = settings.vnstock_api_key
        self.source = settings.vnstock_source
        self.interval = settings.vnstock_interval
        self.length = settings.vnstock_length

    def _history(self, symbol: str) -> pd.DataFrame:
        try:
            from vnstock import Quote
        except Exception as exc:
            raise RuntimeError('vnstock package not available') from exc

        quote = Quote(symbol=symbol, source=self.source)
        df = quote.history(length=self.length, interval=self.interval)
        if df is None or df.empty:
            return pd.DataFrame()
        if 'time' in df.columns:
            df = df.rename(columns={'time': 'date'})
        df['date'] = pd.to_datetime(df['date'])
        df['symbol'] = symbol
        df = df[['date', 'open', 'high', 'low', 'close', 'volume', 'symbol']]
        return df

    def fetch_ohlcv(self, symbols: List[str]) -> pd.DataFrame:
        frames = []
        for sym in symbols:
            df = self._history(sym)
            if not df.empty:
                frames.append(df)
        if not frames:
            return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume', 'symbol'])
        return pd.concat(frames, ignore_index=True)

    def fetch_vnindex(self) -> pd.DataFrame:
        return self._history('VNINDEX')


class SsiProvider(BaseProvider):
    def __init__(self):
        self.base_url = settings.ssi_api_base_url or 'https://iboard-api.ssi.com.vn'
        self.query_url = 'https://iboard-query.ssi.com.vn'
        self.token = settings.ssi_auth_token
        self.device_id = settings.ssi_device_id
        if not self.token or not self.device_id:
            raise RuntimeError('SSI provider requires SSI_AUTH_TOKEN and SSI_DEVICE_ID')
        self.session = requests.Session()
        self.session.headers.update({
            'accept': 'application/json, text/plain, */*',
            'origin': 'https://iboard.ssi.com.vn',
            'referer': 'https://iboard.ssi.com.vn/',
            'user-agent': 'Mozilla/5.0',
            'authorization': f'Bearer {self.token}',
            'device-id': self.device_id
        })

    def fetch_ohlcv(self, symbols: List[str]) -> pd.DataFrame:
        frames = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        from_date = start_date.strftime('%d/%m/%Y')
        to_date = end_date.strftime('%d/%m/%Y')
        for symbol in symbols:
            url = f"{self.base_url}/statistics/company/ssmi/stock-info"
            params = {
                'symbol': symbol.upper(),
                'page': 1,
                'pageSize': 365,
                'fromDate': from_date,
                'toDate': to_date
            }
            try:
                resp = self.session.get(url, params=params, timeout=20)
                resp.raise_for_status()
                data = resp.json()
                if data.get('code') != 'SUCCESS' or not data.get('data'):
                    continue
                df = pd.DataFrame(data['data'])
                if df.empty:
                    continue
                df = df.rename(columns={
                    'tradingDate': 'date',
                    'open': 'open',
                    'high': 'high',
                    'low': 'low',
                    'close': 'close',
                    'volume': 'volume'
                })
                df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
                df['symbol'] = symbol.upper()
                df = df[['date', 'open', 'high', 'low', 'close', 'volume', 'symbol']]
                frames.append(df)
            except Exception as exc:
                logger.warning(f"SSI fetch failed for {symbol}: {exc}")
        if not frames:
            return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume', 'symbol'])
        return pd.concat(frames, ignore_index=True)

    def fetch_vnindex(self) -> pd.DataFrame:
        return self.fetch_ohlcv(['VNINDEX'])


class FireAntProvider(BaseProvider):
    def __init__(self):
        self.base_url = settings.fireant_api_base_url or 'https://restv2.fireant.vn'
        self.token = settings.fireant_bearer_token
        if not self.token:
            raise RuntimeError('FireAnt provider requires FIREANT_BEARER_TOKEN')
        self.headers = {
            'accept': 'application/json, text/plain, */*',
            'authorization': f'Bearer {self.token}',
            'origin': 'https://fireant.vn',
            'referer': 'https://fireant.vn/',
            'user-agent': 'Mozilla/5.0'
        }

    def fetch_ohlcv(self, symbols: List[str]) -> pd.DataFrame:
        frames = []
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        for symbol in symbols:
            url = f"{self.base_url}/symbols/{symbol.upper()}/historical-quotes"
            params = {
                'startDate': start_date,
                'endDate': end_date,
                'offset': 0,
                'limit': 1000
            }
            try:
                resp = requests.get(url, headers=self.headers, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                if not data:
                    continue
                df = pd.DataFrame(data)
                if df.empty:
                    continue
                df = df.rename(columns={
                    'date': 'date',
                    'priceOpen': 'open',
                    'priceHigh': 'high',
                    'priceLow': 'low',
                    'priceClose': 'close',
                    'totalVolume': 'volume'
                })
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                df['symbol'] = symbol.upper()
                df = df[['date', 'open', 'high', 'low', 'close', 'volume', 'symbol']]
                frames.append(df)
            except Exception as exc:
                logger.warning(f"FireAnt fetch failed for {symbol}: {exc}")
        if not frames:
            return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume', 'symbol'])
        return pd.concat(frames, ignore_index=True)

    def fetch_vnindex(self) -> pd.DataFrame:
        return self.fetch_ohlcv(['VNINDEX'])


def get_providers() -> List[BaseProvider]:
    provider = settings.data_provider.lower()
    if provider == 'ssi':
        return [SsiProvider()]
    if provider == 'fireant':
        return [FireAntProvider()]
    if provider == 'vnstock':
        return [VnstockProvider()]
    if provider == 'mock':
        return [MockDataProvider()]
    providers: List[BaseProvider] = []
    for candidate in (SsiProvider, FireAntProvider, VnstockProvider):
        try:
            providers.append(candidate())
        except Exception:
            continue
    if not providers:
        providers = [MockDataProvider()]
    return providers


def get_symbols(session: Session):
    watchlist = [p.symbol for p in session.query(models.Watchlist).all()]
    if watchlist:
        existing = {s.symbol for s in session.query(models.Stock).all()}
        to_add = [sym for sym in watchlist if sym not in existing]
        for sym in to_add:
            session.add(models.Stock(symbol=sym, sector=''))
        if to_add:
            session.commit()
        return watchlist

    symbols = [s.symbol for s in session.query(models.Stock).all()]
    return symbols


def store_ohlcv(session: Session, df: pd.DataFrame):
    if df.empty:
        return
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['date', 'open', 'high', 'low', 'close'])
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
    providers = get_providers()
    remaining = set(symbols)
    frames = []
    for provider in providers:
        logger.info(f'Using provider: {provider.__class__.__name__} for {len(remaining)} symbols')
        if not remaining:
            break
        df = provider.fetch_ohlcv(list(remaining))
        if df is None or df.empty:
            logger.warning(f'Provider {provider.__class__.__name__} returned no data')
            continue
        got = set(df['symbol'].unique()) if 'symbol' in df.columns else set()
        remaining -= got
        logger.info(f'Provider {provider.__class__.__name__} returned {len(df)} rows for {len(got)} symbols')
        frames.append(df)
    if remaining:
        logger.warning(f'No data for symbols: {", ".join(sorted(remaining))}')
    if not frames:
        return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume', 'symbol'])
    df_all = pd.concat(frames, ignore_index=True)
    store_ohlcv(session, df_all)
    return df_all


def fetch_vnindex(session: Session):
    for provider in get_providers():
        df = provider.fetch_vnindex()
        if df is None or df.empty:
            continue
        store_ohlcv(session, df)
        return df
    return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume', 'symbol'])
