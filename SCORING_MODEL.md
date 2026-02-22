# Vietnam Stock Cycle Scoring Model

## Objective
Classify each stock into:

- ACCUMULATION
- MARKUP
- DISTRIBUTION
- MARKDOWN

---

## Rule-Based Logic (Optimized for Vietnam)

### ACCUMULATION

Conditions:
- Price above MA100
- RSI between 40-55
- Volume decreasing trend
- ATR contracting
- Sideway range > 15 sessions

Score Weight:
+2 if volume contraction
+2 if tight range
+1 if MA alignment bullish

---

### MARKUP

Conditions:
- Breakout above 20-day high
- Volume > 150% 20-day avg
- ADX > 25
- RSI > 60

Score Weight:
+3 breakout
+2 volume spike
+1 strong trend

---

### DISTRIBUTION

Conditions:
- RSI > 70
- Bearish divergence
- Volume spike without price progress
- Long upper wick candles

---

### MARKDOWN

Conditions:
- Break MA50
- Volume expansion on red candle
- RSI < 40

---

## Final Output

StockScore:
- Regime label
- Confidence score (0-100)
- RiskReward ratio estimate
- Suggested zone: Buy -> Take Profit