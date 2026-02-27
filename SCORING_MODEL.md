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

## Scoring Engine V2

### Relative Strength (RS)
RS = stock_return_20d - vnindex_return_20d.
Normalize RS to 0–10.

### Volume Momentum
Use a 0–10 score that rewards:
- Rising volume over 5 sessions
- Accumulation pattern detection

### Liquidity Weight
Final Score Formula:
FinalScore =
(TechnicalScore * 0.6) +
(RSScore * 0.2) +
(LiquidityScore * 0.2)

Normalize FinalScore to 0–100.

### Remove Binary Conditions
Replace strict conditions (e.g., RSI between 40–55) with scoring ranges.

### RSI Score Curve (Example)
30–45 → 8 điểm  
45–55 → 10 điểm  
55–65 → 6 điểm

## Synchronization Rules

- No hard filters based on phase; every stock is scored and issued a signal regardless of phase.
- If market_regime == MARKUP, multiply stock_score by 1.1.
- If market_regime == ACCUMULATION, multiply stock_score by 1.05.
- If market_regime == DISTRIBUTION, multiply stock_score by 0.8.
- If market_regime == MARKDOWN, multiply stock_score by 0.7.

## Sector Momentum (Required)

- sector_return_20d
- sector_rs_vs_index
- sector_volume_momentum
- sector_breadth_pct
- Only allow breakout when sector_return_20d > vnindex_return_20d.

## Sector Score

SectorScore (0–10):
- +4 if sector_return_20d > vnindex_return_20d
- +3 if sector_volume_momentum > 0
- +3 if sector_breadth_pct > 55%

FinalScore:

FinalScore =
  Technical * 0.5
+ RS * 0.2
+ Liquidity * 0.12
+ SectorScore * 0.18

## Market Multiplier (Updated)

- MARKUP * 1.1
- ACCUMULATION * 1.05
- DISTRIBUTION * 0.8
- MARKDOWN * 0.7

## Setup Tier

- Tier A: RR > 2.5
- Tier B: RR 1.5–2.5
- Tier C: RR < 1.5

## Trade Signal Generation

- “buy_zone” is deprecated and not returned any more; the system emits an explicit
  entry price for every stock.
- **Entry** is always the latest close price (close must be positive and is never zero).
- **Stop** = entry - 1.5 × ATR; ATR is computed from `atr` field or, if missing, replaced by ma20 or a surrogate derived from the 20‑day high‑low range.
- **Target** = entry + multiplier × ATR where the multiplier depends on breakout strength:
  - `strength = max(0, close / rolling_20_high - 1)`
  - `target_mult = 2 + strength × 5` (so a base of 2 that increases with breakout strength)
- **Risk‑reward** = (target − entry) / (entry − stop) and is therefore dynamic.  It is never a constant 1.5.
- RR, entry, stop and target are always computed for every stock (no hard filters or missing values).
- **Setup quality** metric = score × RR used for ranking opportunities.
- Scores are penalised if phase = DISTRIBUTION (×0.8) or MARKDOWN (×0.6) to deprioritise weak regimes.
- If close ≤ 0 the symbol is skipped.
- A new ``action`` field replaces old setup_status values, computed as:
  * score ≥ 70 → BUY
  * score ≥ 55 → WATCH
  * otherwise → AVOID
- A ``setup_quality`` metric = score × RR is attached for ranking.

## Fake Breakout Filter

- If breakout occurs but close < breakout_level + 1%, reduce score by 30%.
- If volume spike occurs only 1 day, reduce score by 30%.
- Require confirmation over 2 sessions.
