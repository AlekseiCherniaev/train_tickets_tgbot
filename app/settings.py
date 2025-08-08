from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False, frozen=True, env_file=".env", env_ignore_empty=True
    )

    bot_token: str = "BOT_TOKEN"
    log_level: str = "INFO"
    retry_time: int = 9  # seconds for another ticket finding retry
    max_concurrent_searches: int = 3
    request_timeout: float = 3.5
    retry_attempts: int = 7
    # proxy settings
    use_proxy: bool = False
    proxy_login: str = ""
    proxy_password: str = ""
    proxy_host: str = ""
    proxy_port: int = 10500


settings = Settings()
