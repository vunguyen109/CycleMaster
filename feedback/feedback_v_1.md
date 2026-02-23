

## Purpose

This document defines required improvements for the Vietnam Stock Cycle Scanner project.

The goal is to:

- Increase model reliability
- Improve liquidity handling
- Eliminate logical inconsistencies
- Enhance score differentiation
- Make the system production-ready for personal trading

All improvements below are mandatory.

---

# 1. PIPELINE IMPROVEMENTS

## Current Pipeline

Fetch → Feature → Regime → Scoring → Save

## Required New Pipeline

Step 0: Data validation  
Step 1: Liquidity computation & ranking  
Step 2: Liquidity filtering  
Step 3: Feature calculation  
Step 4: Market regime detection  
Step 5: Stock phase detection  
Step 6: Scoring engine  
Step 7: Signal validation  
Step 8: Save results  

---

## 1.1 Data Validation Layer (NEW)

Before any scoring:

- Ensure no missing OHLCV data
- Ensure close > 0
- Ensure volume > 0
- Ensure at least 120 historical sessions

If invalid → skip stock.

---

# 2. LIQUIDITY LAYER (CRITICAL FIX)

## 2.1 Problem

Current liquidity thresholds are too low and produce incorrect classifications.

Bluechip stocks must never be labeled as "Low Liquidity".

---

## 2.2 Required Features (Add to feature_service)

- avg_volume_20
- avg_value_20
- liquidity_percentile_rank
- liquidity_score (0–10)

---

## 2.3 New Liquidity Scoring Table

| Avg Value 20D | Liquidity Score |
|---------------|----------------|
| > 200B       | 10 |
| 100–200B     | 8 |
| 50–100B      | 6 |
| 20–50B       | 4 |
| < 20B        | 0 |

---

## 2.4 Filtering Rule

If avg_value_20 < 20B → exclude from trading setups.

DO NOT classify as regime.  
Mark as:

```

status = "LOW_LIQUIDITY"

```

---

# 3. REGIME & SCORING SYNCHRONIZATION

## 3.1 Problem

Stocks in DISTRIBUTION or MARKDOWN still show buy zones.

This is logically incorrect.

---

## 3.2 Required Rule

If stock_phase in [DISTRIBUTION, MARKDOWN]:

- buy_zone = null
- take_profit = null
- risk_reward = null
- setup_status = "INVALID"

---

## 3.3 Market Alignment Multiplier

If market_regime == MARKUP:
    stock_score *= 1.2

If market_regime == MARKDOWN:
    stock_score *= 0.5

---

# 4. SCORING ENGINE V2

## 4.1 Problem

Too many stocks receive score = 0  
Score differentiation is weak.

---

## 4.2 Required Improvements

### Add Relative Strength

RS = stock_return_20d - vnindex_return_20d

Normalize to score 0–10.

---

### Add Volume Momentum Score

- Rising volume over 5 sessions
- Accumulation pattern detection

---

### Add Liquidity Weight

Final Score Formula:

```

FinalScore =
(TechnicalScore * 0.6) +
(RSScore * 0.2) +
(LiquidityScore * 0.2)

```

Normalize to 0–100.

---

## 4.3 Remove Binary Conditions

Replace strict conditions like:

```

if RSI between 40-55

```

With scoring ranges.

---

# 5. BUY ZONE & RISK MODEL FIX

## 5.1 Problem

buy_zone = 0.0 is unacceptable.

---

## 5.2 Required Behavior

If no valid setup:

```

buy_zone = null
setup_status = "NO_SETUP"

```

Never return zero values.

---

## 5.3 Dynamic Risk Model (Mandatory)

Use ATR-based system:

```

entry = breakout level
stop_loss = entry - 1.5 * ATR
take_profit = entry + 2.5 * ATR
risk_reward = (take_profit - entry) / (entry - stop_loss)

```

---

# 6. FAKE BREAKOUT FILTER

Add rule:

If breakout occurs but:

- close < breakout_level + 1%
- volume spike only 1 day

Reduce score by 30%.

Require confirmation over 2 sessions.

---

# 7. DATABASE SCHEMA UPDATES

Add columns to stock_features:

- avg_volume_20
- avg_value_20
- liquidity_score
- rs_score

Add to stock_scores:

- setup_status
- stop_loss
- market_alignment
- model_version

---

# 8. FRONTEND IMPROVEMENTS REQUIRED

## 8.1 Add Liquidity Badge

Display:
- High
- Medium
- Low

---

## 8.2 Add Setup Status Badge

Display:
- Valid
- Weak
- Invalid
- Low Liquidity

---

## 8.3 Add Market Alignment Indicator

Show if stock aligns with VNINDEX regime.

---

# 9. DEBUGGING REQUIREMENTS

Add logging:

- Number of stocks filtered by liquidity
- Distribution of regimes
- Average score
- Count of valid setups

If >70% stocks in same regime → log warning.

---

# 10. QUALITY CONTROL CHECKS

Before saving results:

- No buy_zone == 0
- No negative risk_reward
- No invalid numeric values
- At least 3 regime categories present (if not, log imbalance)

---

# FINAL GOAL

After applying V2:

- Strong score differentiation
- Liquidity correctly handled
- No invalid price outputs
- Market-aware scoring
- Realistic risk model
- Trading-ready signals

The system must prioritize robustness over signal frequency.
```

