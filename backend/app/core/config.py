from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# app/core/config.py -> backend/app/core -> backend/app -> backend -> repo root
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]

# Prefer a backend-local .env; otherwise use the repository-root .env that is
# already gitignored. This keeps one configuration mechanism for local runs
# started from either `backend/` or the repository root.
ENV_FILE = next(
    (path for path in (BACKEND_DIR / ".env", REPO_ROOT / ".env") if path.is_file()),
    REPO_ROOT / ".env",
)


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    PROJECT_NAME: str = "BreatheWise Backend"

    # API Keys (optional; adapters degrade gracefully when not provided)
    DATA_GOV_IN_API_KEY: Optional[str] = None
    OPENAQ_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    # Service Configuration
    HTTP_TIMEOUT_SECONDS: float = 10.0

    # Rate limiting: memory is zero-config; redis is opt-in and shared across processes
    RATE_LIMIT_STORE: str = "memory"  # "memory" or "redis"
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS: float = 0.1
    REDIS_SOCKET_TIMEOUT_SECONDS: float = 0.2
    REDIS_MAX_CONNECTIONS: int = 10
    CACHE_TTL_SECONDS: int = 900  # 15 minutes cache to avoid redundant API hits
    STALE_DATA_THRESHOLD_HOURS: int = 6

    # CPCB / data.gov.in integration
    CPCB_PAGE_SIZE: int = 100
    CPCB_MAX_PAGES: int = 10
    CPCB_MAX_RETRIES: int = 2
    CPCB_BACKOFF_BASE_SECONDS: float = 0.5
    CPCB_CONNECT_TIMEOUT_SECONDS: float = 5.0
    CPCB_READ_TIMEOUT_SECONDS: float = 20.0
    # Wall-clock ceiling for a single CPCB lookup inside a user request. Without
    # this, retries × pages can exceed a proxy timeout and prevent failover.
    CPCB_REQUEST_BUDGET_SECONDS: float = 3.0
    # After a failed CPCB lookup, skip the provider briefly so follow-up tabs
    # and requests do not each repeat a long, doomed retry chain.
    CPCB_CIRCUIT_BREAKER_SECONDS: float = 60.0
    CPCB_CACHE_TTL_SECONDS: int = 300
    CPCB_LAST_VALID_MAX_HOURS: int = 24
    CPCB_FRESH_HOURS: int = 2
    CPCB_DELAYED_HOURS: int = 6
    CPCB_MIN_OFFLINE_STATION_SAMPLE: int = 5
    # Set true only after the dataset's averaging period has been verified for
    # the deployed feed. Until then CPCB AQI stays unavailable rather than
    # mislabelling an unverified average as an official CPCB AQI.
    CPCB_AVERAGING_PERIOD_VERIFIED: bool = False

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
