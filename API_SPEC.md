# API Specification

## GET /market/regime

Return:
{
  regime: "MARKUP",
  confidence: 78
}

---

## GET /stocks/top

Return:
[
  {
    symbol,
    regime,
    score,
    buy_zone,
    take_profit,
    risk_reward
  }
]

---

## GET /stocks/{symbol}

Return:
{
  features,
  regime,
  score,
  suggested_trade
}

---

## GET /scan/latest

Return latest scan summary