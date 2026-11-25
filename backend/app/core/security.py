import logging
import math
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, Dict, List

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Enforces security headers across all responses to prevent XSS, clickjacking,
    and MIME-type sniffing.
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(self), microphone=(), camera=()"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class RateLimitStore(ABC):
    """Counter storage for the rate limiter.

    ``check`` returns ``(allowed, retry_after_seconds)``. ``retry_after_seconds``
    is only meaningful when ``allowed`` is False.
    """

    async def setup(self) -> None:
        """Optional lazy initialization hook (no-op for stores needing none)."""

    @abstractmethod
    async def check(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        """Atomically record one request for ``key`` and decide if it is allowed."""

    @abstractmethod
    async def reset(self) -> None:
        """Clear counters (used by tests)."""


class InMemoryRateLimitStore(RateLimitStore):
    """Single-process sliding-window store; zero configuration required."""

    def __init__(self) -> None:
        # client identifier -> list of request timestamps
        self.clients: Dict[str, List[float]] = defaultdict(list)

    async def check(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        now = time.time()
        window_start = now - window_seconds

        timestamps = [ts for ts in self.clients[key] if ts > window_start]
        if timestamps:
            self.clients[key] = timestamps
        else:
            self.clients.pop(key, None)

        if len(timestamps) >= max_requests:
            retry_after = int(timestamps[0] + window_seconds - now) + 1
            return False, max(1, retry_after)

        self.clients[key].append(now)
        return True, 0

    async def reset(self) -> None:
        self.clients.clear()


# A single Redis round trip: increment, attach a TTL to a new counter, and
# return the counter plus remaining TTL so Retry-After does not need a second
# command. The TTL guarantees a key is removed once its window has elapsed.
_REDIS_RATE_LIMIT_SCRIPT = """
local current = redis.call("INCR", KEYS[1])
if current == 1 then
    redis.call("PEXPIRE", KEYS[1], ARGV[1])
end
local ttl_ms = redis.call("PTTL", KEYS[1])
return {current, ttl_ms}
"""


class RedisRateLimitStore(RateLimitStore):
    """Shared fixed-window store backed by Redis.

    ``redis.asyncio`` is imported only in ``setup`` so deployments using the
    default in-memory store have no Redis dependency at import time. Inject
    ``client`` to test without a server.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        *,
        client: Any | None = None,
        key_prefix: str = "ratelimit:",
    ) -> None:
        # Never include this URL in log messages: it may contain credentials.
        self.redis_url = redis_url if redis_url is not None else settings.REDIS_URL
        self.key_prefix = key_prefix
        self._client = client
        self._client_owned = False

    async def setup(self) -> None:
        if self._client is not None:
            return
        try:
            import redis.asyncio as redis_asyncio
        except ImportError as exc:  # pragma: no cover - depends on deployment deps
            raise RuntimeError("RATE_LIMIT_STORE=redis requires the redis package") from exc

        self._client = redis_asyncio.from_url(
            self.redis_url,
            socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
        )
        self._client_owned = True

    async def check(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        if self._client is None:
            await self.setup()

        window_ms = max(1, int(window_seconds * 1000))
        current, ttl_ms = await self._client.eval(
            _REDIS_RATE_LIMIT_SCRIPT, 1, f"{self.key_prefix}{key}", window_ms
        )
        current = int(current)
        ttl_ms = int(ttl_ms)
        if current <= max_requests:
            return True, 0

        retry_after = max(1, math.ceil(ttl_ms / 1000)) if ttl_ms > 0 else max(1, window_seconds)
        return False, retry_after

    async def reset(self) -> None:
        if self._client is None:
            return
        keys = [key async for key in self._client.scan_iter(match=f"{self.key_prefix}*", count=100)]
        if keys:
            await self._client.delete(*keys)

    async def close(self) -> None:
        if self._client_owned and self._client is not None:
            await self._client.aclose()
            self._client_owned = False


def create_rate_limit_store() -> RateLimitStore:
    """Build the store selected by ``RATE_LIMIT_STORE`` (default: memory)."""
    configured_store = settings.RATE_LIMIT_STORE.strip().lower()
    if configured_store == "memory":
        return InMemoryRateLimitStore()
    if configured_store == "redis":
        return RedisRateLimitStore()
    raise ValueError(
        f"Unsupported RATE_LIMIT_STORE={configured_store!r}; expected 'memory' or 'redis'"
    )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiter per client IP, backed by a pluggable store.

    Protects externally accessible endpoints against abusive traffic. Store
    errors are fail-open: a rate-limiter outage must not take the API down.
    """

    def __init__(
        self,
        app,
        max_requests: int = 120,
        window_seconds: int = 60,
        store: RateLimitStore | None = None,
    ):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.store = store if store is not None else create_rate_limit_store()
        self._store_ready = False

    @property
    def clients(self) -> Dict[str, List[float]]:
        """Backward-compatible view of the legacy in-memory counter dict."""
        return self.store.clients if isinstance(self.store, InMemoryRateLimitStore) else {}

    def reset(self) -> None:
        """Resets the rate limiter cache (useful for testing)."""
        # Async stores cannot be reset synchronously; the in-memory reset is
        # the behavior this helper historically provided.
        if isinstance(self.store, InMemoryRateLimitStore):
            self.store.clients.clear()

    async def dispatch(self, request: Request, call_next):
        # Exclude internal health checks from aggressive rate limiting
        if request.url.path in ("/health", "/api/v1/health"):
            return await call_next(request)

        # Never trust a client-supplied IP header: it is trivially spoofable.
        client_ip = request.client.host if request.client else "unknown"
        try:
            if not self._store_ready:
                await self.store.setup()
                self._store_ready = True
            allowed, retry_after = await self.store.check(
                client_ip, self.max_requests, self.window_seconds
            )
        except Exception:
            # Do not log the exception: driver errors can embed REDIS_URL,
            # including its password. Deliberately fail open (see docs).
            logger.warning("Rate-limit store unavailable; allowing request (fail-open)")
            return await call_next(request)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Too many requests. Please retry in {retry_after} seconds.",
                },
                headers={"Retry-After": str(max(1, retry_after))},
            )

        return await call_next(request)
