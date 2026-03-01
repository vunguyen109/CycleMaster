from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = 'CycleMaster'
    database_url: str = 'sqlite:///./data/cyclemaster.db'
    data_provider: str = 'mock'
    ssi_auth_token: str = ''
    ssi_device_id: str = ''
    ssi_api_base_url: str = ''
    fireant_bearer_token: str = ''
    fireant_api_base_url: str = ''
    vnstock_api_key: str = ''
    vnstock_source: str = 'VCI'
    vnstock_interval: str = '1D'
    vnstock_length: str = '1Y'
    vnstock_batch_size: int = 50
    vnstock_sleep_seconds: int = 0
    x_fiin_key: str = ''
    x_fiin_seed: str = ''
    x_fiin_user_id: str = ''
    x_fiin_user_token: str = ''
    schedule_hour: int = 18
    schedule_minute: int = 30
    top_n: int = 5
    liquidity_min_avg_volume: int = 200000
    liquidity_min_avg_value: float = 20_000_000_000
    liquidity_min_scan_value: float = 5_000_000_000
    lookback_min: int = 150
    min_universe_size: int = 150
    universe_files: str = 'data/universe_vn30.txt,data/universe_hnx30.txt,data/universe_midcap.txt'
    sector_map_file: str = 'data/sector_map.csv'
    top_percentile: float = 0.95
    top_sector_cap: int = 3
    top_sector_window: int = 10
    weight_technical: float = 0.5
    weight_rs: float = 0.2
    weight_liquidity: float = 0.12
    weight_sector: float = 0.18
    # Cycle-aware scoring weights and tuning
    weight_cycle: float = 0.0
    cycle_boost: float = 0.10
    cycle_mid_penalty_threshold: float = 0.2
    cycle_mid_penalty: float = 0.25
    # Backtest / execution tuning
    trade_cost_pct: float = 0.0
    slippage_pct: float = 0.0
    cycle_buy_threshold: float = 0.25
    cycle_sell_threshold: float = 0.75
    cycle_amplitude_min: float = 1e-6
    log_level: str = 'INFO'
    portfolio_symbols: str = ''
    portfolio_quantities: str = ''
    portfolio_avg_price: str = ''

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')


settings = Settings()
