from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://guess:guess_password@localhost:5432/guess"

    # JWT Authentication — ⚠️ MUST change for production!
    secret_key: str = "change-me-to-a-random-secret-key"
    jwt_secret: str = "change-me-to-a-different-random-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # CORS
    cors_origins: List[str] = ["http://localhost:5173"]

    # QQ avatars (fetched server-side so QQ numbers are never sent to browsers)
    qq_avatar_url: str = "https://q1.qlogo.cn/g?b=qq&nk={qq}&s=100"
    avatar_cache_seconds: int = 6 * 60 * 60
    avatar_failure_cache_seconds: int = 5 * 60
    avatar_fetch_timeout_seconds: float = 5.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
