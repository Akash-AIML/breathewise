import ipaddress
from pathlib import Path

from pydantic import model_validator
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
    DATA_GOV_IN_API_KEY: str | None = None
    OPENAQ_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None

    # Free-tier Gemini model chain, tried in order. A rate-limited, unavailable,
    # or malformed response on one model never blocks the next one.
    GEMINI_MODELS: str = (
        "gemini-3.1-flash-lite,gemini-3.5-flash-lite,gemma-4-31b-it,gemma-4-26b-a4b-it"
    )
    # Wall-clock ceiling for the whole LLM chain so a slow failover cannot
    # exceed the frontend proxy timeout. Per-model timeouts are listed below.
    LLM_REQUEST_BUDGET_SECONDS: float = 20.0
    GEMINI_MODEL_TIMEOUT_SECONDS: float = 10.0
    GEMMA_MODEL_TIMEOUT_SECONDS: float = 12.0

    # Service Configuration
    HTTP_TIMEOUT_SECONDS: float = 10.0

    # Rate limiting: memory is zero-config; redis is opt-in and shared across processes
    RATE_LIMIT_STORE: str = "memory"  # "memory" or "redis"
    RATE_LIMIT_MAX_REQUESTS: int = 120
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    # Expensive endpoints get a tighter bucket in addition to the global limit.
    RATE_LIMIT_ASSISTANT_REQUESTS: int = 10
    RATE_LIMIT_LOCATION_REQUESTS: int = 20
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS: float = 0.1
    REDIS_SOCKET_TIMEOUT_SECONDS: float = 0.2
    REDIS_MAX_CONNECTIONS: int = 10
    CACHE_TTL_SECONDS: int = 900  # 15 minutes cache to avoid redundant API hits
    CACHE_MAX_ENTRIES: int = 1000  # bound attacker-controlled coordinate keys
    CPCB_MAX_LOCKS: int = 500
    API_MAX_PAGE_SIZE: int = 500  # server-enforced ceiling for list endpoints
    STALE_DATA_THRESHOLD_HOURS: int = 6

    # CPCB / data.gov.in integration
    CPCB_PAGE_SIZE: int = 100
    CPCB_MAX_PAGES: int = 10
    CPCB_MAX_RETRIES: int = 2
    CPCB_BACKOFF_BASE_SECONDS: float = 0.5
    CPCB_CONNECT_TIMEOUT_SECONDS: float = 5.0
    CPCB_READ_TIMEOUT_SECONDS: float = 20.0
    # Wall-clock ceiling for a single CPCB lookup inside a user request. Without
    # this, retries x pages can exceed a proxy timeout and prevent failover.
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
    # Only these peers may supply X-Forwarded-For / X-Real-IP. Empty is safest.
    TRUSTED_PROXY_IPS: list[str] = []

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        if "*" in self.CORS_ORIGINS:
            raise ValueError("Wildcard CORS origins are not allowed with credentials")
        if self.ENVIRONMENT.lower() == "production":
            for origin in self.CORS_ORIGINS:
                if not origin.startswith("https://"):
                    raise ValueError("Production CORS origins must use HTTPS")
        for address in self.TRUSTED_PROXY_IPS:
            try:
                ipaddress.ip_address(address)
            except ValueError as exc:
                raise ValueError(f"Invalid TRUSTED_PROXY_IPS entry: {address}") from exc
        return self

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
