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
    buy_zone, // nullable when setup invalid
    take_profit, // nullable when setup invalid
    risk_reward, // nullable when setup invalid
    liquidity_score,
    setup_status,
    market_alignment,
    setup_tier
  }
]

Notes:
- Top list is generated from the universe scan (VN30, HNX30, Midcap).
- Filters out LOW_LIQUIDITY and non-prospective regimes.
- Uses percentile ranking (top 5% universe) instead of absolute score.
- Sector cap: max 3 symbols per sector within top 10 window.

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
