import numpy as np
import pandas as pd
from app.models import models


def _prepare_df(session, symbol):
    rows = session.query(models.OHLCV).filter_by(symbol=symbol).order_by(models.OHLCV.date).all()
    if not rows:
        return None
    df = pd.DataFrame([{
        'date': r.date,
        'open': r.open,
        'high': r.high,
        'low': r.low,
        'close': r.close,
        'volume': r.volume
    } for r in rows])
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma50'] = df['close'].rolling(50).mean()
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    df['vol_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
    df['high20'] = df['high'].rolling(20).max()
    return df


def _compute_metrics(trades, equity_curve):
    wins = [t for t in trades if t['pnl'] > 0]
    win_rate = len(wins) / max(len(trades), 1)
    peak = equity_curve[0]
    drawdown = 0.0
    for e in equity_curve:
        peak = max(peak, e)
        drawdown = min(drawdown, (e - peak) / peak)
    avg_rr = np.mean([t['rr'] for t in trades]) if trades else 0.0
    return win_rate, abs(drawdown), avg_rr


def backtest_breakout20(df: pd.DataFrame):
    trades = []
    equity = 1.0
    equity_curve = [equity]
    position = None

    for i in range(21, len(df)):
        row = df.iloc[i]
        if position is None:
            if row['close'] > df['high20'].iloc[i-1] and row['vol_ratio'] > 1.5:
                entry = row['close']
                stop = entry - 1.5 * row['atr']
                target = entry + 3.0 * row['atr']
                position = {'entry': entry, 'stop': stop, 'target': target}
        else:
            price = row['close']
            if price <= position['stop'] or price >= position['target'] or price < row['ma20']:
                pnl = (price - position['entry']) / position['entry']
                rr = (position['target'] - position['entry']) / max(position['entry'] - position['stop'], 0.01)
                equity *= (1 + pnl)
                equity_curve.append(equity)
                trades.append({'pnl': pnl, 'rr': rr})
                position = None

    return trades, equity_curve


def backtest_accumulation_spike(df: pd.DataFrame):
    trades = []
    equity = 1.0
    equity_curve = [equity]
    position = None

    for i in range(30, len(df)):
        row = df.iloc[i]
        range_width = (df['high'].iloc[i-15:i].max() - df['low'].iloc[i-15:i].min()) / row['close']
        accumulation = range_width < 0.06 and df['vol_ratio'].iloc[i-10:i].mean() < 0.9
        if position is None:
            if accumulation and row['vol_ratio'] > 1.5 and row['close'] > df['high'].iloc[i-15:i].max():
                entry = row['close']
                stop = entry - 1.5 * row['atr']
                target = entry + 3.0 * row['atr']
                position = {'entry': entry, 'stop': stop, 'target': target}
        else:
            price = row['close']
            if price <= position['stop'] or price >= position['target'] or price < row['ma50']:
                pnl = (price - position['entry']) / position['entry']
                rr = (position['target'] - position['entry']) / max(position['entry'] - position['stop'], 0.01)
                equity *= (1 + pnl)
                equity_curve.append(equity)
                trades.append({'pnl': pnl, 'rr': rr})
                position = None

    return trades, equity_curve


def run_backtest(session, symbol: str, strategy: str):
    df = _prepare_df(session, symbol)
    if df is None:
        return None
    if strategy == 'breakout20':
        trades, equity_curve = backtest_breakout20(df)
    else:
        trades, equity_curve = backtest_accumulation_spike(df)
    win_rate, max_dd, avg_rr = _compute_metrics(trades, equity_curve)
    return {
        'symbol': symbol,
        'strategy': strategy,
        'win_rate': float(win_rate),
        'max_drawdown': float(max_dd),
        'avg_rr': float(avg_rr),
        'equity_curve': [{'step': i, 'equity': float(e)} for i, e in enumerate(equity_curve)]
    }
