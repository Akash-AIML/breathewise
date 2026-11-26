"""Regressions for the key-handling and endpoint-abuse hardening pass."""

import io
import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Request
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.adapters.cpcb import CPCBAdapter
from app.core.config import Settings, settings
from app.core.redaction import (
    REDACTED,
    SecretRedactionFilter,
    redact_text,
)
from app.core.security import (
    RateLimitMiddleware,
    RateLimitStore,
    RedisRateLimitStore,
    SecurityHeadersMiddleware,
)
from app.main import http_exception_handler
from app.services.air_quality_service import AirQualityService


def _starlette_app(path: str = "/", methods: list[str] | None = None):
    async def ok(_request):
        return PlainTextResponse("ok")

    return Starlette(routes=[Route(path, ok, methods=methods or ["GET"])])


class RecordingStore(RateLimitStore):
    def __init__(self) -> None:
        self.check_mock = AsyncMock(return_value=(True, 0))

    async def setup(self) -> None:
        return None

    async def check(self, key: str, max_requests: int, window_seconds: int):
        return await self.check_mock(key, max_requests, window_seconds)

    async def reset(self) -> None:
        return None


class FailingRedis:
    def __init__(self) -> None:
        self.calls = 0

    async def eval(self, *_args, **_kwargs):
        self.calls += 1
        raise ConnectionError("simulated Redis outage")


def test_redaction_removes_configured_and_pattern_secrets(monkeypatch):
    monkeypatch.setattr(settings, "DATA_GOV_IN_API_KEY", "data-gov-secret-1234")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "gemini-secret-5678")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "groq-secret-9999")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://user:redis-secret@cache:6379/0")

    text = (
        "GET /resource?api-key=data-gov-secret-1234&format=json "
        "x-goog-api-key: gemini-secret-5678 "
        "Authorization: Bearer groq-secret-9999 "
        "redis://user:redis-secret@cache:6379/0"
    )
    redacted = redact_text(text)

    for secret in (
        "data-gov-secret-1234",
        "gemini-secret-5678",
        "groq-secret-9999",
        "redis-secret",
    ):
        assert secret not in redacted
    assert redacted.count(REDACTED) >= 4


def test_logging_filter_redacts_message_and_traceback(monkeypatch):
    secret = "traceback-secret-4242"  # noqa: S105 - fake secret for redaction test
    monkeypatch.setattr(settings, "GEMINI_API_KEY", secret)
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.addFilter(SecretRedactionFilter())
    logger = logging.getLogger("breathewise.test.redaction")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.ERROR)
    logger.addHandler(handler)

    try:
        raise RuntimeError(f"upstream failed with x-api-key={secret}")
    except RuntimeError:
        logger.error("request failed: api_key=%s", secret, exc_info=True)
    finally:
        logger.removeHandler(handler)

    logs = output.getvalue()
    assert secret not in logs
    assert REDACTED in logs
    assert "Traceback" in logs


@pytest.mark.asyncio
async def test_http_error_detail_is_redacted(monkeypatch):
    secret = "error-detail-secret-7777"  # noqa: S105 - fake secret for redaction test
    monkeypatch.setattr(settings, "OPENAQ_API_KEY", secret)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],
        "query_string": b"",
        "client": ("testclient", 123),
        "server": ("testserver", 80),
    }
    request = Request(scope)

    response = await http_exception_handler(
        request, HTTPException(status_code=400, detail=f"invalid api_key={secret}")
    )
    body = response.body.decode()

    assert secret not in body
    assert REDACTED in body


def test_security_settings_reject_unsafe_configuration():
    with pytest.raises(ValueError, match="Wildcard CORS"):
        Settings(_env_file=None, CORS_ORIGINS=["*"])
    with pytest.raises(ValueError, match="HTTPS"):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            CORS_ORIGINS=["http://frontend.example"],
        )
    with pytest.raises(ValueError, match="TRUSTED_PROXY_IPS"):
        Settings(_env_file=None, TRUSTED_PROXY_IPS=["not-an-ip"])


@pytest.mark.asyncio
async def test_security_headers_set_page_and_api_policies():
    limiter = SecurityHeadersMiddleware(_starlette_app("/api/v1/health"))
    async with AsyncClient(transport=ASGITransport(app=limiter), base_url="http://test") as client:
        api_response = await client.get("/api/v1/health")
        page_response = await client.get("/")

    assert api_response.headers["X-Frame-Options"] == "DENY"
    assert "geolocation=(self)" in api_response.headers["Permissions-Policy"]
    assert api_response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert api_response.headers["Cache-Control"] == "no-store"
    assert "Cache-Control" not in page_response.headers


@pytest.mark.asyncio
async def test_expensive_routes_use_separate_rate_limit_buckets():
    store = RecordingStore()
    limiter = RateLimitMiddleware(
        _starlette_app("/api/v1/assistant/chat", ["POST"]),
        max_requests=100,
        window_seconds=60,
        store=store,
        path_limits={"/api/v1/assistant/chat": 2, "/api/v1/locations/search": 3},
    )
    async with AsyncClient(transport=ASGITransport(app=limiter), base_url="http://test") as client:
        assert (await client.post("/api/v1/assistant/chat")).status_code == 200
        assert (await client.get("/api/v1/locations/search")).status_code == 404
        assert (await client.get("/global")).status_code == 404

    calls = [call.args for call in store.check_mock.await_args_list]
    assert calls[0][0].endswith(":/api/v1/assistant/chat")
    assert calls[0][1] == 2
    assert calls[1][0].endswith(":/api/v1/locations/search")
    assert calls[1][1] == 3
    # Global routes keep the original per-client key and are unaffected by the
    # narrower assistant/location buckets.
    assert ":" not in calls[2][0]
    assert calls[2][1] == 100


@pytest.mark.asyncio
async def test_forwarded_ip_header_is_trusted_only_from_configured_proxy():
    store = RecordingStore()
    limiter = RateLimitMiddleware(
        _starlette_app(),
        store=store,
        trusted_proxies=["10.0.0.1"],
    )
    transport = ASGITransport(app=limiter, client=("10.0.0.1", 5000))
    async with AsyncClient(transport=transport, base_url="http://proxy") as client:
        await client.get("/", headers={"X-Forwarded-For": "203.0.113.9, 10.0.0.1"})

    assert store.check_mock.await_args.args[0] == "203.0.113.9"

    direct_store = RecordingStore()
    direct = RateLimitMiddleware(_starlette_app(), store=direct_store, trusted_proxies=["10.0.0.1"])
    direct_transport = ASGITransport(app=direct, client=("198.51.100.4", 5000))
    async with AsyncClient(transport=direct_transport, base_url="http://direct") as client:
        await client.get("/", headers={"X-Forwarded-For": "203.0.113.9"})

    assert direct_store.check_mock.await_args.args[0] == "198.51.100.4"


@pytest.mark.asyncio
async def test_redis_outage_still_throttles_expensive_route(caplog):
    failing = FailingRedis()
    store = RedisRateLimitStore(
        redis_url="redis://user:redis-secret@127.0.0.1:6379/0", client=failing
    )
    limiter = RateLimitMiddleware(
        _starlette_app("/api/v1/assistant/chat", ["POST"]),
        max_requests=100,
        window_seconds=60,
        store=store,
        path_limits={"/api/v1/assistant/chat": 2},
    )
    async with AsyncClient(transport=ASGITransport(app=limiter), base_url="http://test") as client:
        statuses = [(await client.post("/api/v1/assistant/chat")).status_code for _ in range(3)]

    assert statuses == [200, 200, 429]
    assert failing.calls == 3
    assert "local fallback" in caplog.text
    assert "redis-secret" not in caplog.text


@pytest.mark.asyncio
async def test_air_quality_cache_is_bounded_and_expires_entries(monkeypatch, clean_observation):
    monkeypatch.setattr(settings, "CACHE_MAX_ENTRIES", 5)
    service = AirQualityService()
    service.cpcb_adapter.fetch_by_coordinates = AsyncMock(return_value=None)
    service.openaq_adapter.fetch_by_coordinates = AsyncMock(return_value=None)
    service.openmeteo_adapter.fetch_by_coordinates = AsyncMock(return_value=clean_observation)

    for index in range(20):
        await service.get_air_quality_for_coordinates(10 + index / 100, 20 + index / 100)

    assert len(service._cache) == 5

    stale_key = next(iter(service._cache))
    service._cache[stale_key].expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await service.get_air_quality_for_coordinates(40.0, 50.0)
    assert stale_key not in service._cache


def test_cpcb_per_key_locks_are_bounded(monkeypatch):
    monkeypatch.setattr(settings, "CPCB_MAX_LOCKS", 3)
    adapter = CPCBAdapter(api_key="test-key", station_registry=[])
    for index in range(25):
        adapter._lock_for(f"city-{index}")
    assert len(adapter._locks) == 3
