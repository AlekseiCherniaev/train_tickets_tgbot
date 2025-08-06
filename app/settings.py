from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False, frozen=True, env_file=".env", env_ignore_empty=True
    )

    bot_token: str = "BOT_TOKEN"
    log_level: str = "INFO"
    retry_time: int = 5  # seconds for another ticket finding retry
    max_concurrent_searches: int = 3


settings = Settings()
