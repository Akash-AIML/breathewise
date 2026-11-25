# Rate limiting

The API rate limiter is a `RateLimitMiddleware` in `backend/app/core/security.py`. It counts
requests per client IP and returns HTTP 429 with `error_code=RATE_LIMIT_EXCEEDED` and a
`Retry-After` header when the limit is reached. `/health` and `/api/v1/health` are exempt.

Only `request.client.host` is used as the client identity; client-supplied IP headers are
ignored because they are trivially spoofable.

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `RATE_LIMIT_STORE` | `memory` | `memory` (zero-config default) or `redis` (opt-in, shared across processes). |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL. May contain credentials; never logged. |
| `REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS` | `0.1` | Bounded connection timeout. |
| `REDIS_SOCKET_TIMEOUT_SECONDS` | `0.2` | Bounded socket read/write timeout. |
| `REDIS_MAX_CONNECTIONS` | `10` | Bound on the async connection pool. |

Set these as environment variables (or in the backend-local `.env`). An unknown
`RATE_LIMIT_STORE` raises a startup error rather than silently changing behavior.

The default memory store needs no extra package. For the Redis store, install
`redis` (`pip install -r backend/requirements.txt` includes it). `redis.asyncio` is imported
lazily inside `RedisRateLimitStore.setup()`, so the application never imports Redis when the
memory store is selected.

The middleware still takes `max_requests` and `window_seconds` arguments (defaults 120 and 60
seconds, as configured in `backend/app/main.py`). A custom store can be injected for tests.

## Semantics

- **Memory store (default):** sliding window per process, preserving the original behavior.
  With N workers, each worker enforces its own limit, so the effective global limit is
  approximately N × `max_requests`.
- **Redis store (opt-in):** shared fixed window across every process/worker. A single Lua
  script performs `INCR` on `ratelimit:<ip>`, sets `PEXPIRE` to the window when the counter is
  created, and returns the counter plus `PTTL` for `Retry-After`. One round trip means the
  increment is atomic across processes; the TTL guarantees keys are removed after the window,
  so counters do not leak. The returned TTL is used directly in `Retry-After`.
- `RateLimitMiddleware.dispatch` always awaits the store's `check` method.

## Redis outage policy: fail-open

If the store's `setup` or `check` raises (Redis down, timeout, missing driver, etc.), the
request is allowed through and a generic warning is logged. This keeps a rate-limiter outage
from becoming a full API outage; the trade-off is that abusive traffic is temporarily not
throttled while Redis is unavailable. The same policy applies to any store error. The log
message intentionally excludes the exception details because driver errors can embed
`REDIS_URL` and its password.

## Verification status and tests

Unit tests in `backend/tests/unit/test_security_rate_limit.py` use a fake async Redis client:

- in-memory store still enforces the limit and `reset()` clears it;
- Redis store issues one atomic `eval` per request, uses the Lua `INCR`/`PEXPIRE`/`PTTL`
  script, passes the window as milliseconds, and uses the TTL for `Retry-After`;
- a simulated Redis connection failure results in requests being allowed (fail-open) and no
  credentials in the logs;
- config selects the expected store, and an unknown store value is rejected.

**Live Redis was not verified in this environment.** No Redis server was started and no
integration test against a real Redis instance was run; the Redis path is validated only with
a fake async client and mocked commands.
