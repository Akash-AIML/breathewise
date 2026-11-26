import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx

from app.core.cache import bound_locks, enforce_limit, prune_expired
from app.core.config import settings
from app.schemas.cpcb import CPCBStationObservation
from app.schemas.observation import DataQualityStatus

logger = logging.getLogger(__name__)

# httpx logs full request URLs at INFO. data.gov.in requires api-key as a query
# parameter, so INFO logging would leak the secret into application logs.
logging.getLogger("httpx").setLevel(logging.WARNING)

REDACTED = "REDACTED"
_SECRET_QUERY = re.compile(r"(api-key=)[^&\s]+", re.IGNORECASE)


class CPCBConfigurationError(RuntimeError):
    """Raised when CPCB is required but not configured."""


class CPCBProviderError(RuntimeError):
    """Base class for upstream CPCB failures with redacted messages."""


class CPCBRateLimitError(CPCBProviderError):
    pass


class CPCBTemporaryError(CPCBProviderError):
    pass


class CPCBResponseError(CPCBProviderError):
    pass


def redact_secrets(value: object) -> str:
    """Remove api-key query values from any text before logging or returning it."""
    return _SECRET_QUERY.sub(r"\1" + REDACTED, str(value))


def _parse_cpcb_page_response(response: httpx.Response) -> tuple[list[dict[str, Any]], int | None]:
    """Validate and extract records and total count from a CPCB HTTP 200 response."""
    try:
        payload = response.json()
    except ValueError:
        raise CPCBResponseError("CPCB provider returned invalid JSON.") from None

    if not isinstance(payload, dict):
        raise CPCBResponseError("CPCB provider returned a non-object payload.")
    records = payload.get("records")
    if not isinstance(records, list):
        raise CPCBResponseError("CPCB provider response has no records list.")
    total = payload.get("total")
    return records, int(total) if isinstance(total, (int, str)) and str(total).isdigit() else None


class CPCBTransportMixin:
    """HTTP requests, caching, and circuit-breaker helpers for CPCBAdapter."""

    api_key: str | None
    BASE_URL: str
    RESOURCE_ID: str
    _cache: dict[str, tuple[datetime, Any]]
    _last_valid: dict[str, tuple[datetime, list[CPCBStationObservation]]]
    _locks: dict[str, asyncio.Lock]
    _circuit_open_until: datetime | None

    if TYPE_CHECKING:

        @staticmethod
        def _with_current_freshness(
            observation: CPCBStationObservation,
        ) -> CPCBStationObservation: ...

    # ── HTTP client ──────────────────────────────────────────────────────────

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=settings.CPCB_CONNECT_TIMEOUT_SECONDS,
                read=settings.CPCB_READ_TIMEOUT_SECONDS,
                write=settings.CPCB_CONNECT_TIMEOUT_SECONDS,
                pool=settings.CPCB_CONNECT_TIMEOUT_SECONDS,
            )
        )

    @staticmethod
    def _retry_delay(attempt: int, retry_after: str = "") -> float:
        if retry_after.isdigit():
            return min(float(retry_after), 10.0)
        return float(settings.CPCB_BACKOFF_BASE_SECONDS * (2**attempt))

    async def _send_page_request(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: dict[str, Any],
        attempt: int,
        max_attempts: int,
    ) -> httpx.Response | None:
        try:
            response = await client.get(url, params=params)
        except httpx.TimeoutException:
            if attempt + 1 < max_attempts:
                await asyncio.sleep(self._retry_delay(attempt))
                return None
            raise CPCBTemporaryError("CPCB provider timed out.") from None
        except httpx.TransportError:
            if attempt + 1 < max_attempts:
                await asyncio.sleep(self._retry_delay(attempt))
                return None
            raise CPCBTemporaryError("CPCB provider network failure.") from None

        if response.status_code == 429:
            if attempt + 1 < max_attempts:
                await asyncio.sleep(
                    self._retry_delay(attempt, response.headers.get("Retry-After", ""))
                )
                return None
            raise CPCBRateLimitError("CPCB provider rate limit exceeded.")
        if response.status_code in {500, 502, 503, 504}:
            if attempt + 1 < max_attempts:
                await asyncio.sleep(self._retry_delay(attempt))
                return None
            raise CPCBTemporaryError(f"CPCB provider HTTP {response.status_code}.")
        if response.status_code != 200:
            raise CPCBProviderError(f"CPCB provider HTTP {response.status_code}.")
        return response

    async def _request_page(
        self, params: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], int | None]:
        """Fetch one page with bounded retries. Never logs the credentialed URL."""
        if not self.api_key:
            raise CPCBConfigurationError("DATA_GOV_IN_API_KEY is not configured.")

        url = f"{self.BASE_URL}/{self.RESOURCE_ID}"
        request_params = {"api-key": self.api_key, "format": "json", **params}
        max_attempts = max(1, settings.CPCB_MAX_RETRIES + 1)

        async with self._client() as client:
            for attempt in range(max_attempts):
                response = await self._send_page_request(
                    client, url, request_params, attempt, max_attempts
                )
                if response is not None:
                    return _parse_cpcb_page_response(response)

        raise CPCBTemporaryError("CPCB provider retries exhausted.")

        raise CPCBTemporaryError("CPCB provider request exhausted retries.")

    async def _fetch_pages(
        self,
        filters: dict[str, str] | None = None,
        max_pages: int | None = None,
        page_size: int | None = None,
    ) -> tuple[list[dict[str, Any]], int | None]:
        size = page_size or settings.CPCB_PAGE_SIZE
        pages = max_pages or settings.CPCB_MAX_PAGES
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        offset = 0
        reported_total: int | None = None

        for _ in range(pages):
            params: dict[str, Any] = {"limit": size, "offset": offset}
            params.update(filters or {})
            page, total = await self._request_page(params)
            reported_total = total if total is not None else reported_total
            if not page:
                break
            for record in page:
                fingerprint = str(sorted((str(k), str(v)) for k, v in record.items()))
                if fingerprint not in seen:
                    seen.add(fingerprint)
                    records.append(record)
            if reported_total is not None and offset + len(page) >= reported_total:
                break
            offset += len(page)

        return records, reported_total

    # ── Caching ──────────────────────────────────────────────────────────────

    def _cache_key(self, label: str) -> str:
        return label

    def _cached(self, key: str) -> Any | None:
        entry = self._cache.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if datetime.now(UTC) >= expires_at:
            self._cache.pop(key, None)
            return None
        if isinstance(value, list) and all(
            isinstance(item, CPCBStationObservation) for item in value
        ):
            return [self._with_current_freshness(obs) for obs in value]
        return value

    def _store(self, key: str, value: Any) -> None:
        expires = datetime.now(UTC) + timedelta(seconds=settings.CPCB_CACHE_TTL_SECONDS)
        self._cache[key] = (expires, value)
        prune_expired(self._cache, lambda entry: entry[0])
        enforce_limit(self._cache, settings.CACHE_MAX_ENTRIES)
        if (
            isinstance(value, list)
            and value
            and all(isinstance(item, CPCBStationObservation) for item in value)
        ):
            self._last_valid[key] = (datetime.now(UTC), value)
            prune_expired(
                self._last_valid,
                lambda entry: entry[0] + timedelta(hours=settings.CPCB_LAST_VALID_MAX_HOURS),
            )
            enforce_limit(self._last_valid, settings.CACHE_MAX_ENTRIES)

    @staticmethod
    def _as_stale(
        observations: list[CPCBStationObservation], reason: str
    ) -> list[CPCBStationObservation]:
        stale: list[CPCBStationObservation] = []
        for observation in observations:
            warnings = [w for w in observation.warnings if w != reason]
            warnings.append(reason)
            stale.append(
                observation.model_copy(
                    update={"freshness": DataQualityStatus.STALE, "warnings": warnings}
                )
            )
        return stale

    def _previous_valid(self, key: str) -> list[CPCBStationObservation] | None:
        entry = self._last_valid.get(key)
        if not entry:
            return None
        saved_at, observations = entry
        if datetime.now(UTC) - saved_at > timedelta(hours=settings.CPCB_LAST_VALID_MAX_HOURS):
            self._last_valid.pop(key, None)
            return None
        return self._as_stale(observations, "Refresh failed; showing the last valid observation.")

    def _circuit_is_open(self) -> bool:
        if self._circuit_open_until is None:
            return False
        if datetime.now(UTC) < self._circuit_open_until:
            return True
        self._circuit_open_until = None
        return False

    def _trip_circuit(self) -> None:
        if self._circuit_open_until is not None:
            return
        self._circuit_open_until = datetime.now(UTC) + timedelta(
            seconds=settings.CPCB_CIRCUIT_BREAKER_SECONDS
        )
        logger.warning(
            "CPCBAdapter skipping provider for %.1fs after an upstream failure.",
            settings.CPCB_CIRCUIT_BREAKER_SECONDS,
        )

    def _unavailable_or_stale(self, key: str, reason: str) -> Any:
        previous = self._previous_valid(key)
        if previous is not None:
            logger.warning("CPCBAdapter using stale cache for %s: %s", key, reason)
            return previous
        raise CPCBTemporaryError(reason)

    async def _load_with_fallback(self, key: str, loader) -> Any:
        """Cache + coalesce requests, preserving the last valid data on failure.

        A wall-clock budget bounds retries x pagination so a provider outage can
        never hold up the user-facing request or block downstream providers.
        """
        cached = self._cached(key)
        if cached is not None:
            return cached
        if self._circuit_is_open():
            return self._unavailable_or_stale(key, "CPCB provider is temporarily unavailable.")
        async with self._lock_for(key):
            cached = self._cached(key)
            if cached is not None:
                return cached
            if self._circuit_is_open():
                return self._unavailable_or_stale(key, "CPCB provider is temporarily unavailable.")
            try:
                async with asyncio.timeout(settings.CPCB_REQUEST_BUDGET_SECONDS):
                    value = await loader()
            except (TimeoutError, CPCBProviderError) as exc:
                self._trip_circuit()
                reason = (
                    "CPCB provider exceeded the request time budget."
                    if isinstance(exc, TimeoutError)
                    else redact_secrets(exc)
                )
                return self._unavailable_or_stale(key, reason)
            self._circuit_open_until = None
            if not value:
                previous = self._previous_valid(key)
                return previous if previous is not None else value
            self._store(key, value)
            return value

    def _lock_for(self, key: str) -> asyncio.Lock:
        # Leave room for the new lock so the configured cap is exact.
        bound_locks(self._locks, settings.CPCB_MAX_LOCKS - 1)
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]
