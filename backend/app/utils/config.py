from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = 'CycleMaster'
    database_url: str = 'sqlite:///./data/cyclemaster.db'
    data_provider: str = 'mock'
    schedule_hour: int = 18
    schedule_minute: int = 30
    top_n: int = 5
    liquidity_min_avg_volume: int = 200000
    log_level: str = 'INFO'
    portfolio_symbols: str = ''
    portfolio_quantities: str = ''
    portfolio_avg_price: str = ''

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')


settings = Settings()
