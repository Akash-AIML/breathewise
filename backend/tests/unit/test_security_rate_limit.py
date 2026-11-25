from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.core.config import Settings, settings
from app.core.security import (
    InMemoryRateLimitStore,
    RateLimitMiddleware,
    RateLimitStore,
    RedisRateLimitStore,
    create_rate_limit_store,
)


def _inner_app() -> Starlette:
    async def ok(request):
        return PlainTextResponse("ok")

    return Starlette(routes=[Route("/", ok)])


class FakeAsyncRedis:
    """Minimal async client double: records the Lua call and simulates counters."""

    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expiries: dict[str, int] = {}
        self.eval_calls: list[tuple[str, int, str, int]] = []

    async def eval(self, script: str, numkeys: int, key: str, ttl_ms: int) -> list[int]:
        self.eval_calls.append((script, numkeys, key, ttl_ms))
        count = self.values.get(key, 0) + 1
        self.values[key] = count
        if count == 1:
            self.expiries[key] = ttl_ms
        return [count, self.expiries.get(key, -1)]


class FailingAsyncRedis:
    """Async client double whose every command fails (simulated outage)."""

    def __init__(self) -> None:
        self.eval_calls = 0

    async def eval(self, *args, **kwargs):
        self.eval_calls += 1
        raise ConnectionError("simulated Redis outage")


class RecordingStore(RateLimitStore):
    def __init__(self) -> None:
        self.check_mock = AsyncMock(return_value=(True, 0))

    async def setup(self) -> None:
        pass

    async def check(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        return await self.check_mock(key, max_requests, window_seconds)

    async def reset(self) -> None:
        pass


def test_config_defaults_are_zero_config_memory(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_STORE", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    defaults = Settings(_env_file=None)

    assert defaults.RATE_LIMIT_STORE == "memory"
    assert defaults.REDIS_URL == "redis://localhost:6379/0"
    assert defaults.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS > 0
    assert defaults.REDIS_SOCKET_TIMEOUT_SECONDS > 0
    assert defaults.REDIS_MAX_CONNECTIONS > 0


@pytest.mark.parametrize(
    ("configured", "expected_type"),
    [("memory", InMemoryRateLimitStore), ("redis", RedisRateLimitStore)],
)
def test_config_selects_store(monkeypatch, configured, expected_type):
    monkeypatch.setattr(settings, "RATE_LIMIT_STORE", configured)

    assert isinstance(create_rate_limit_store(), expected_type)
    middleware = RateLimitMiddleware(_inner_app(), max_requests=2, window_seconds=60)
    assert isinstance(middleware.store, expected_type)


def test_unknown_store_is_rejected_without_importing_redis(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_STORE", "memcached")

    with pytest.raises(ValueError, match="RATE_LIMIT_STORE"):
        create_rate_limit_store()


@pytest.mark.asyncio
async def test_memory_store_still_enforces_limit():
    store = InMemoryRateLimitStore()
    limiter = RateLimitMiddleware(_inner_app(), max_requests=2, window_seconds=60, store=store)

    async with AsyncClient(transport=ASGITransport(app=limiter), base_url="http://test") as client:
        assert (await client.get("/")).status_code == 200
        assert (await client.get("/")).status_code == 200
        blocked = await client.get("/")

    assert blocked.status_code == 429
    assert blocked.json()["error_code"] == "RATE_LIMIT_EXCEEDED"
    assert 1 <= int(blocked.headers["Retry-After"]) <= 60
    assert sum(len(timestamps) for timestamps in store.clients.values()) == 2

    limiter.reset()
    assert store.clients == {}
    async with AsyncClient(transport=ASGITransport(app=limiter), base_url="http://test") as client:
        assert (await client.get("/")).status_code == 200


@pytest.mark.asyncio
async def test_redis_store_uses_atomic_increment_and_honours_ttl():
    fake = FakeAsyncRedis()
    store = RedisRateLimitStore(client=fake)

    assert await store.check("1.2.3.4", 2, 60) == (True, 0)
    assert await store.check("1.2.3.4", 2, 60) == (True, 0)
    assert await store.check("1.2.3.4", 2, 60) == (False, 60)

    assert len(fake.eval_calls) == 3
    script, numkeys, key, ttl_ms = fake.eval_calls[0]
    assert numkeys == 1
    assert key == "ratelimit:1.2.3.4"
    assert ttl_ms == 60_000
    assert "INCR" in script
    assert "PEXPIRE" in script
    assert "PTTL" in script
    assert fake.expiries == {key: 60_000}
    assert {call[2] for call in fake.eval_calls} == {key}


@pytest.mark.asyncio
async def test_redis_outage_fails_open_without_logging_credentials(caplog):
    failing = FailingAsyncRedis()
    store = RedisRateLimitStore(
        redis_url="redis://user:supersecret@127.0.0.1:6379/0", client=failing
    )
    limiter = RateLimitMiddleware(_inner_app(), max_requests=1, window_seconds=60, store=store)

    async with AsyncClient(transport=ASGITransport(app=limiter), base_url="http://test") as client:
        for _ in range(3):
            assert (await client.get("/")).status_code == 200

    assert failing.eval_calls == 3
    assert "fail-open" in caplog.text
    assert "supersecret" not in caplog.text
    assert "redis://" not in caplog.text


@pytest.mark.asyncio
async def test_middleware_awaits_store_check():
    store = RecordingStore()
    limiter = RateLimitMiddleware(_inner_app(), max_requests=2, window_seconds=60, store=store)

    async with AsyncClient(transport=ASGITransport(app=limiter), base_url="http://test") as client:
        assert (await client.get("/")).status_code == 200

    store.check_mock.assert_awaited_once()
    assert store.check_mock.await_args.args[1:] == (2, 60)
