# Daily Scan Pipeline

## Execution Time
18:30 daily after market close

---

## Steps

1. Fetch VNINDEX + all stock data
2. Calculate features
3. Detect market regime
4. Apply scoring model
5. Save results
6. Update Top 5 opportunity list

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