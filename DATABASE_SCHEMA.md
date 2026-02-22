# Database Schema

Table: market_regime
- id
- date
- regime
- confidence

Table: stocks
- id
- symbol
- sector

Table: stock_features
- stock_id
- date
- rsi
- macd
- adx
- volume_ratio
- atr
- ma20
- ma50
- ma100

Table: stock_scores
- stock_id
- date
- regime
- score
- buy_zone
- tp_zone
- risk_reward