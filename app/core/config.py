from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Paw of Help API"
    api_prefix: str = "/api/v1"
    secret_key: str = "change-this-secret-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    database_url: str = "postgresql+psycopg://paw:paw@localhost:5432/paw_of_help"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    media_dir: str = "media"
    media_url_prefix: str = "/media"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    seed_demo_data: bool = True
    verification_token_expire_hours: int = 24
    yandex_geocoder_api_key: str | None = None
    redis_url: str | None = None
    cache_ttl_animals_catalogs: int = 1200
    cache_ttl_static_catalogs: int = 2700
    cache_ttl_knowledge_article: int = 600
    cache_ttl_org_public: int = 180
    cache_ttl_animals_list: int = 45


settings = Settings()
