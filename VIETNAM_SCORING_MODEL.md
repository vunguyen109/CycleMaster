# Vietnam Optimized Cycle Model

Designed for:
- Midcap liquidity
- Sector rotation
- Short-term speculation

---

## ACCUMULATION

Conditions:
- Price above MA100
- RSI 40–55
- Volume decreasing 10 sessions
- ATR contracting
- Sideway range > 15 days

Score Logic:
Range 0-10

---

## MARKUP (Breakout)

Conditions:
- Break 20-day high
- Volume > 150% avg
- ADX > 25
- RSI > 60

High confidence if:
- VNINDEX regime = Markup

---

## DISTRIBUTION

Conditions:
- RSI > 70
- Bearish divergence
- Volume spike but no price progress
- Long upper wick candles

---

## MARKDOWN

Conditions:
- Break MA50
- Volume spike on red candle
- RSI < 40

---

## Final Output

For each stock:

{
  symbol,
  regime,
  confidence_score,
  buy_zone,
  take_profit_zone,
  risk_reward
}