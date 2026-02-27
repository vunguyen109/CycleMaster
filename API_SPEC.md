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
    action,             // BUY/WATCH/AVOID
    entry,              // price used for calculation
    stop,               // defined as close - 2*ATR
    target,             // defined as close + 3*ATR
    rr,                 // risk-reward ratio
    setup_quality,      // score * rr
    liquidity_score,
    setup_status,       // legacy field retains same value as action
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
