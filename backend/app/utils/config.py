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
    x_fiin_key: str = ''
    x_fiin_seed: str = ''
    x_fiin_user_id: str = ''
    x_fiin_user_token: str = ''
    schedule_hour: int = 18
    schedule_minute: int = 30
    top_n: int = 5
    liquidity_min_avg_volume: int = 200000
    liquidity_min_avg_value: float = 1_000_000_000
    log_level: str = 'INFO'
    portfolio_symbols: str = ''
    portfolio_quantities: str = ''
    portfolio_avg_price: str = ''

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')


settings = Settings()
