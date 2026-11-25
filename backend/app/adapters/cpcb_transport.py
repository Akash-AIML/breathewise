import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

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


class CPCBTransportMixin:
    """HTTP requests, caching, and circuit-breaker helpers for CPCBAdapter."""

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

    async def _request_page(
        self, params: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        """Fetch one page with bounded retries. Never logs the credentialed URL."""
        if not self.api_key:
            raise CPCBConfigurationError("DATA_GOV_IN_API_KEY is not configured.")

        url = f"{self.BASE_URL}/{self.RESOURCE_ID}"
        request_params = {"api-key": self.api_key, "format": "json", **params}
        max_attempts = max(1, settings.CPCB_MAX_RETRIES + 1)

        async with self._client() as client:
            for attempt in range(max_attempts):
                try:
                    response = await client.get(url, params=request_params)
                except httpx.TimeoutException:
                    if attempt + 1 < max_attempts:
                        await asyncio.sleep(settings.CPCB_BACKOFF_BASE_SECONDS * (2**attempt))
                        continue
                    raise CPCBTemporaryError("CPCB provider timed out.") from None
                except httpx.TransportError:
                    if attempt + 1 < max_attempts:
                        await asyncio.sleep(settings.CPCB_BACKOFF_BASE_SECONDS * (2**attempt))
                        continue
                    raise CPCBTemporaryError("CPCB provider network failure.") from None

                if response.status_code == 429:
                    if attempt + 1 < max_attempts:
                        retry_after = response.headers.get("Retry-After", "")
                        delay = (
                            float(retry_after)
                            if retry_after.isdigit()
                            else settings.CPCB_BACKOFF_BASE_SECONDS * (2**attempt)
                        )
                        await asyncio.sleep(min(delay, 10.0))
                        continue
                    raise CPCBRateLimitError("CPCB provider rate limit exceeded.")

                if response.status_code in {500, 502, 503, 504}:
                    if attempt + 1 < max_attempts:
                        await asyncio.sleep(settings.CPCB_BACKOFF_BASE_SECONDS * (2**attempt))
                        continue
                    raise CPCBTemporaryError(f"CPCB provider HTTP {response.status_code}.")

                if response.status_code in {400, 401, 403}:
                    # Permanent failures must not be retried.
                    raise CPCBProviderError(
                        f"CPCB provider rejected the request (HTTP {response.status_code})."
                    )

                if response.status_code != 200:
                    raise CPCBProviderError(f"CPCB provider HTTP {response.status_code}.")

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
                return records, int(total) if isinstance(total, (int, str)) and str(
                    total
                ).isdigit() else None

        raise CPCBTemporaryError("CPCB provider request exhausted retries.")

    async def _fetch_pages(
        self,
        filters: Optional[Dict[str, str]] = None,
        max_pages: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        size = page_size or settings.CPCB_PAGE_SIZE
        pages = max_pages or settings.CPCB_MAX_PAGES
        records: List[Dict[str, Any]] = []
        seen: set[str] = set()
        offset = 0
        reported_total: Optional[int] = None

        for _ in range(pages):
            params: Dict[str, Any] = {"limit": size, "offset": offset}
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

    def _cached(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if datetime.now(timezone.utc) >= expires_at:
            return None
        if isinstance(value, list) and all(
            isinstance(item, CPCBStationObservation) for item in value
        ):
            return [self._with_current_freshness(obs) for obs in value]
        return value

    def _store(self, key: str, value: Any) -> None:
        expires = datetime.now(timezone.utc) + timedelta(seconds=settings.CPCB_CACHE_TTL_SECONDS)
        self._cache[key] = (expires, value)
        if (
            isinstance(value, list)
            and value
            and all(isinstance(item, CPCBStationObservation) for item in value)
        ):
            self._last_valid[key] = (datetime.now(timezone.utc), value)

    @staticmethod
    def _as_stale(
        observations: List[CPCBStationObservation], reason: str
    ) -> List[CPCBStationObservation]:
        stale: List[CPCBStationObservation] = []
        for observation in observations:
            warnings = [w for w in observation.warnings if w != reason]
            warnings.append(reason)
            stale.append(
                observation.model_copy(
                    update={"freshness": DataQualityStatus.STALE, "warnings": warnings}
                )
            )
        return stale

    def _previous_valid(self, key: str) -> Optional[List[CPCBStationObservation]]:
        entry = self._last_valid.get(key)
        if not entry:
            return None
        saved_at, observations = entry
        if datetime.now(timezone.utc) - saved_at > timedelta(
            hours=settings.CPCB_LAST_VALID_MAX_HOURS
        ):
            return None
        return self._as_stale(observations, "Refresh failed; showing the last valid observation.")

    def _circuit_is_open(self) -> bool:
        if self._circuit_open_until is None:
            return False
        if datetime.now(timezone.utc) < self._circuit_open_until:
            return True
        self._circuit_open_until = None
        return False

    def _trip_circuit(self) -> None:
        if self._circuit_open_until is not None:
            return
        self._circuit_open_until = datetime.now(timezone.utc) + timedelta(
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

        A wall-clock budget bounds retries × pagination so a provider outage can
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
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]
