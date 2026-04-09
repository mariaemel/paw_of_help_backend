from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Paw of Help API"
    api_prefix: str = "/api/v1"
    secret_key: str = "change-this-secret-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    database_url: str = "sqlite:///./paw_of_help.db"
    media_dir: str = "media"
    media_url_prefix: str = "/media"
    seed_demo_data: bool = True


settings = Settings()
