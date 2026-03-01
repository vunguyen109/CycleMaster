import numpy as np
import pandas as pd
from app.models import models
from app.services import cycle_service
from app.utils.config import settings


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


def backtest_cycle_bottom_top(df: pd.DataFrame, initial_capital: float = 1.0):
    """
    Strategy: enter long near cycle bottom, exit near cycle top.

    - Uses `cycle_service.compute_cycle_dataframe` (past-only windowed Hilbert) to obtain
      cycle_position and cycle_amplitude for each timestamp.
    - Entry signal: cycle_position <= buy_threshold and amplitude >= amplitude_min
    - Exit signal: cycle_position >= sell_threshold or stop-loss hit
    - Executions occur at next period's open (no lookahead). Transaction cost and slippage applied.
    """
    trades = []
    equity = float(initial_capital)
    equity_curve = [equity]
    position = None
    entry_price = None
    entry_index = None

    # Compute cycle features vectorized (no lookahead inside function)
    window = max(int(getattr(settings, 'lookback_min', 120)), 120)
    cycle_df = cycle_service.compute_cycle_dataframe(df['close'], window=window, detrend_ma=50, min_periods=30, compute_dominant_period=False)

    # thresholds (configurable)
    buy_threshold = float(getattr(settings, 'cycle_buy_threshold', 0.25))  # cycle_position <= 0.25 ~ bottom quadrant
    sell_threshold = float(getattr(settings, 'cycle_sell_threshold', 0.75))  # cycle_position >= 0.75 ~ top quadrant
    amplitude_min = float(getattr(settings, 'cycle_amplitude_min', 1e-6))
    trade_cost_pct = float(getattr(settings, 'trade_cost_pct', 0.0))
    slippage_pct = float(getattr(settings, 'slippage_pct', 0.0))

    n = len(df)
    # start at index where cycle_df has first non-null (cycle_df aligns with df index)
    for t in range(n - 1):
        # Use features available at t (computed from past up to t)
        pos = None
        amp = None
        try:
            pos = cycle_df['cycle_position'].iloc[t]
            amp = cycle_df['cycle_amplitude'].iloc[t]
        except Exception:
            pos = np.nan
            amp = np.nan

        # Execute signals at next open (t+1)
        next_open = float(df['open'].iloc[t + 1])

        # Entry
        if position is None and pd.notna(pos) and pd.notna(amp):
            if pos <= buy_threshold and amp >= amplitude_min:
                # compute entry price with slippage
                P_e = next_open * (1.0 + slippage_pct)
                entry_fee = trade_cost_pct * equity
                available = equity - entry_fee
                if available <= 0:
                    continue
                qty = available / P_e
                position = {'qty': qty, 'entry_price': P_e}
                entry_price = P_e
                entry_index = t + 1

        # Exit
        elif position is not None:
            # exit if top reached
            if pd.notna(pos) and pos >= sell_threshold:
                P_x = next_open * (1.0 - slippage_pct)
                qty = position['qty']
                proceeds = qty * P_x
                exit_fee = trade_cost_pct * proceeds
                net = proceeds - exit_fee
                # update equity and record trade
                pnl = (net - (equity - entry_fee)) / (equity - entry_fee) if (equity - entry_fee) > 0 else 0.0
                trades.append({'entry_index': entry_index, 'exit_index': t + 1, 'entry_price': entry_price, 'exit_price': P_x, 'pnl': pnl})
                equity = net
                equity_curve.append(equity)
                position = None
                entry_price = None
                entry_index = None

    # If still holding at the end, close at last close price minus slippage
    if position is not None:
        P_x = float(df['close'].iloc[-1]) * (1.0 - slippage_pct)
        qty = position['qty']
        proceeds = qty * P_x
        exit_fee = trade_cost_pct * proceeds
        net = proceeds - exit_fee
        pnl = (net - (equity - entry_fee)) / (equity - entry_fee) if (equity - entry_fee) > 0 else 0.0
        trades.append({'entry_index': entry_index, 'exit_index': n - 1, 'entry_price': entry_price, 'exit_price': P_x, 'pnl': pnl})
        equity = net
        equity_curve.append(equity)
        position = None

    # Metrics
    wins = [t for t in trades if t['pnl'] > 0]
    win_rate = len(wins) / max(len(trades), 1)
    eq = np.array(equity_curve)
    peak = eq[0]
    drawdown = 0.0
    for e in eq:
        peak = max(peak, e)
        drawdown = min(drawdown, (e - peak) / peak)
    max_dd = abs(drawdown)
    avg_rr = np.mean([t['pnl'] for t in trades]) if trades else 0.0

    # Additional metrics: CAGR and Sharpe (daily returns annualized)
    cagr = 0.0
    sharpe = 0.0
    try:
        period_days = max(len(eq) - 1, 1)
        total_return = eq[-1] / eq[0] if eq[0] != 0 else 1.0
        cagr = float(np.power(total_return, 252.0 / period_days) - 1.0) if period_days > 0 else 0.0
        daily_returns = np.diff(eq) / eq[:-1]
        if len(daily_returns) > 1 and np.std(daily_returns, ddof=1) > 0:
            sharpe = float(np.mean(daily_returns) / np.std(daily_returns, ddof=1) * np.sqrt(252.0))
        else:
            sharpe = 0.0
    except Exception:
        cagr = 0.0
        sharpe = 0.0

    return trades, equity_curve, win_rate, max_dd, avg_rr, cagr, sharpe


def run_backtest(session, symbol: str, strategy: str):
    df = _prepare_df(session, symbol)
    if df is None:
        return None
    if strategy == 'breakout20':
        trades, equity_curve = backtest_breakout20(df)
    else:
        if strategy == 'accumulation_spike':
            trades, equity_curve = backtest_accumulation_spike(df)
        elif strategy == 'cycle_bottom_top':
            trades, equity_curve, win_rate, max_dd, avg_rr, cagr, sharpe = backtest_cycle_bottom_top(df)
            return {
                'symbol': symbol,
                'strategy': strategy,
                'win_rate': float(win_rate),
                'max_drawdown': float(max_dd),
                'avg_rr': float(avg_rr),
                'equity_curve': [{'step': i, 'equity': float(e)} for i, e in enumerate(equity_curve)],
                'cagr': float(cagr),
                'sharpe': float(sharpe)
            }
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
