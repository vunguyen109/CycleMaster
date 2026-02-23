# VueJS Frontend Specification

## Folder Structure

frontend/
│
├── src/
│   ├── views/
│   ├── components/
│   ├── services/
│   ├── router/
│   └── store/
│
└── vite.config.js

---

## Pages

1. Dashboard
2. Market Regime
3. Top Opportunities
4. Stock Detail

---

## Dashboard Widgets

- Current Market Regime
- Top 5 Accumulation
- Top 5 Breakout
- Warning (Distribution / Markdown)
- VNINDEX chart
- Liquidity badge (High/Medium/Low)
- Setup status badge (Valid/Weak/Invalid/Low Liquidity)
- Market alignment indicator

---

## Stock Detail Page

- Candlestick chart (ECharts)
- Volume
- Regime label
- Confidence score
- Suggested Buy → TP
- RiskReward
- Liquidity badge
- Setup status badge
- Market alignment indicator
- Setup tier (A/B/C)
