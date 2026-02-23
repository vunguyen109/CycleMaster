# Daily Scan Pipeline

## Execution Time
18:30 daily after market close

---

## Steps

0. Data validation (OHLCV completeness, close > 0, volume > 0, >= 120 sessions)
1. Liquidity computation & ranking
2. Liquidity filtering (scan universe > 5B/day, min 150 symbols)
3. Feature calculation
4. Market regime detection
5. Stock phase detection
6. Scoring engine
7. Signal validation
8. Save results + update Top 5 opportunity list

---

## Debugging Requirements

- Log number of stocks filtered by liquidity.
- Log distribution of regimes.
- Log average score.
- Log count of valid setups.
- If > 70% stocks in same regime, log warning.

---

## Quality Control Checks

- Ensure no buy_zone == 0.
- Ensure no negative risk_reward.
- Ensure no invalid numeric values.
- Ensure at least 3 regime categories present (if not, log imbalance).

---

## Universe Ranking

- Use percentile ranking over universe scores.
- Publish top 5% universe.
- Cap top list to max 3 symbols per sector (within top 10 window).

---

## Required Features

Price:
- MA20 / MA50 / MA100
- MA slope
- 20-day high breakout

Volume:
- Volume ratio (current / 20d avg)
- OBV trend

Momentum:
- RSI(14)
- MACD histogram
- ADX(14)

Volatility:
- ATR contraction
