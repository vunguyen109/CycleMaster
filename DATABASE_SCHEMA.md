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
- avg_volume_20
- avg_value_20
- liquidity_score
- liquidity_percentile_rank
- rs_score
- sector_return_20d
- sector_rs_vs_index
- sector_volume_momentum
- sector_breadth_pct

Table: stock_scores
- stock_id
- date
- regime  # also aliased as phase in some outputs
- score
- tp_zone  # legacy, may be unused
- risk_reward
- stop_loss
- confidence
- setup_status  # now contains action (BUY/WATCH/AVOID)
- market_alignment
- model_version
- setup_tier

# note: entry/target/rr/setup_quality are not stored in the current schema;
# they are computed on demand from close prices and stored risk_reward/stop_loss.
