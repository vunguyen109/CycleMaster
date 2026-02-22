import pandas as pd
from sqlalchemy.orm import Session
from app.utils import indicators
from app.models import models


def calculate_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values('date').copy()
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma50'] = df['close'].rolling(50).mean()
    df['ma100'] = df['close'].rolling(100).mean()
    df['rsi'] = indicators.rsi(df['close'])
    macd_line, _, macd_hist = indicators.macd(df['close'])
    df['macd'] = macd_hist
    df['adx'] = indicators.adx(df['high'], df['low'], df['close'])
    df['atr'] = indicators.atr(df['high'], df['low'], df['close'])
    df['volume_ratio'] = indicators.volume_ratio(df['volume'])
    return df


def save_features(session: Session, symbol: str, df: pd.DataFrame):
    stock = session.query(models.Stock).filter_by(symbol=symbol).first()
    if not stock:
        return
    for _, row in df.iterrows():
        if pd.isna(row['ma20']) or pd.isna(row['rsi']):
            continue
        exists = session.query(models.StockFeatures).filter_by(stock_id=stock.id, date=row['date'].date()).first()
        if exists:
            continue
        session.add(models.StockFeatures(
            stock_id=stock.id,
            date=row['date'].date(),
            rsi=float(row['rsi']),
            macd=float(row['macd']),
            adx=float(row['adx']),
            volume_ratio=float(row['volume_ratio']),
            atr=float(row['atr']),
            ma20=float(row['ma20']),
            ma50=float(row['ma50']),
            ma100=float(row['ma100'])
        ))
    session.commit()
