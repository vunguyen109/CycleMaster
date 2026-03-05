import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.utils import indicators
from app.services import liquidity_service
from app.models import models
from app.services import cycle_service
from app.utils.config import settings


def calculate_features(df: pd.DataFrame, lookback: int | None = None) -> pd.DataFrame:
    df = df.sort_values('date').copy()
    if lookback is not None and lookback > 0:
        df = df.tail(lookback).copy()
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma50'] = df['close'].rolling(50).mean()
    df['ma100'] = df['close'].rolling(100).mean()
    df['ma200'] = df['close'].rolling(200).mean()
    df['ma20_slope'] = df['ma20'].diff(5)
    df['ma50_slope'] = df['ma50'].diff(5)
    df['ma100_slope'] = df['ma100'].diff(5)
    df['ma200_slope'] = df['ma200'].diff(5)
    df['rsi'] = indicators.rsi(df['close'])
    macd_line, _, macd_hist = indicators.macd(df['close'])
    df['macd'] = macd_hist
    df['adx'] = indicators.adx(df['high'], df['low'], df['close'])
    df['atr'] = indicators.atr(df['high'], df['low'], df['close'])
    df['volume_ratio'] = indicators.volume_ratio(df['volume'])
    df['volume_trend_5'] = df['volume'].rolling(5).mean() / df['volume'].rolling(20).mean()
    df['avg_volume_20'] = df['volume'].rolling(20).mean()
    df['avg_value_20'] = (df['close'] * 1000 * df['volume']).rolling(20).mean()
    df['atr_percent'] = (df['atr'] / df['close']).replace([pd.NA, float('inf'), float('-inf')], float('nan')) * 100.0
    df['liquidity_score'] = df['avg_value_20'].apply(liquidity_service.liquidity_score_from_avg_value)
    df['liquidity_percentile_rank'] = float('nan')
    df['rs_score'] = float('nan')
    df['sector_return_20d'] = float('nan')
    df['sector_rs_vs_index'] = float('nan')
    df['sector_volume_momentum'] = float('nan')
    df['sector_breadth_pct'] = float('nan')
    df['sector_score'] = float('nan')
    # Compute cycle features only for the most recent point (uses only past data)
    try:
        window = max(int(getattr(settings, 'lookback_min', 150)), 120)
        cycle = cycle_service.compute_cycle_for_series(df['close'], window=window, min_points=60)
        df['cycle_phase'] = float('nan')
        df['cycle_amplitude'] = float('nan')
        df['dominant_cycle_period'] = float('nan')
        if cycle:
            df.at[df.index[-1], 'cycle_phase'] = cycle.get('cycle_phase')
            df.at[df.index[-1], 'cycle_amplitude'] = cycle.get('cycle_amplitude')
            df.at[df.index[-1], 'dominant_cycle_period'] = cycle.get('dominant_period')
    except Exception:
        df['cycle_phase'] = float('nan')
        df['cycle_amplitude'] = float('nan')
        df['dominant_cycle_period'] = float('nan')

    return df


def save_features(session: Session, symbol: str, df: pd.DataFrame):
    stock = session.query(models.Stock).filter_by(symbol=symbol).first()
    if not stock:
        return
    latest_date = session.query(func.max(models.StockFeatures.date)).filter_by(stock_id=stock.id).scalar()
    if latest_date is not None:
        # Keep the latest day for upsert so same-day rescans can refresh derived fields.
        df = df[df['date'] >= pd.Timestamp(latest_date)]
    if df.empty:
        return
    for _, row in df.iterrows():
        if pd.isna(row['ma20']) or pd.isna(row['rsi']):
            continue
        row_date = row['date'].date()
        exists = session.query(models.StockFeatures).filter_by(stock_id=stock.id, date=row_date).first()
        payload = {
            'rsi': float(row['rsi']),
            'macd': float(row['macd']),
            'adx': float(row['adx']),
            'volume_ratio': float(row['volume_ratio']),
            'atr': float(row['atr']),
            'ma20': float(row['ma20']),
            'ma50': float(row['ma50']),
            'ma100': float(row['ma100']),
            'ma200': float(row['ma200']) if 'ma200' in row and not pd.isna(row['ma200']) else None,
            'ma20_slope': float(row['ma20_slope']) if 'ma20_slope' in row and not pd.isna(row['ma20_slope']) else None,
            'ma50_slope': float(row['ma50_slope']) if 'ma50_slope' in row and not pd.isna(row['ma50_slope']) else None,
            'ma100_slope': float(row['ma100_slope']) if 'ma100_slope' in row and not pd.isna(row['ma100_slope']) else None,
            'ma200_slope': float(row['ma200_slope']) if 'ma200_slope' in row and not pd.isna(row['ma200_slope']) else None,
            'volume_trend_5': float(row['volume_trend_5']) if 'volume_trend_5' in row and not pd.isna(row['volume_trend_5']) else None,
            'atr_percent': float(row['atr_percent']) if 'atr_percent' in row and not pd.isna(row['atr_percent']) else None,
            'avg_volume_20': float(row['avg_volume_20']),
            'avg_value_20': float(row['avg_value_20']),
            'liquidity_score': float(row['liquidity_score']),
            'liquidity_percentile_rank': float(row['liquidity_percentile_rank']) if not pd.isna(row['liquidity_percentile_rank']) else None,
            'rs_score': float(row['rs_score']) if 'rs_score' in row and not pd.isna(row['rs_score']) else None,
            'sector_return_20d': float(row['sector_return_20d']) if 'sector_return_20d' in row and not pd.isna(row['sector_return_20d']) else None,
            'sector_rs_vs_index': float(row['sector_rs_vs_index']) if 'sector_rs_vs_index' in row and not pd.isna(row['sector_rs_vs_index']) else None,
            'sector_volume_momentum': float(row['sector_volume_momentum']) if 'sector_volume_momentum' in row and not pd.isna(row['sector_volume_momentum']) else None,
            'sector_breadth_pct': float(row['sector_breadth_pct']) if 'sector_breadth_pct' in row and not pd.isna(row['sector_breadth_pct']) else None,
            'sector_score': float(row['sector_score']) if 'sector_score' in row and not pd.isna(row['sector_score']) else None
        }
        # Add cycle fields (may be present only on latest row)
        payload['cycle_phase'] = float(row['cycle_phase']) if 'cycle_phase' in row and not pd.isna(row['cycle_phase']) else None
        payload['cycle_amplitude'] = float(row['cycle_amplitude']) if 'cycle_amplitude' in row and not pd.isna(row['cycle_amplitude']) else None
        payload['dominant_cycle_period'] = float(row['dominant_cycle_period']) if 'dominant_cycle_period' in row and not pd.isna(row['dominant_cycle_period']) else None
        if exists:
            for key, value in payload.items():
                setattr(exists, key, value)
        else:
            session.add(models.StockFeatures(
                stock_id=stock.id,
                date=row_date,
                **payload
            ))
    session.commit()
