from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    PROJECT_NAME: str = "BreatheWise Backend"

    # API Keys (optional; adapters gracefully degrade when not provided)
    DATA_GOV_IN_API_KEY: Optional[str] = None
    OPENAQ_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    # Service Configuration
    HTTP_TIMEOUT_SECONDS: float = 10.0
    CACHE_TTL_SECONDS: int = 900  # 15 minutes cache to avoid redundant API hits
    STALE_DATA_THRESHOLD_HOURS: int = 6

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
