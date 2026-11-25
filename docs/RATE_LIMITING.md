# Rate limiting

The API rate limiter is a `RateLimitMiddleware` in `backend/app/core/security.py`. It counts
requests per client IP and returns HTTP 429 with `error_code=RATE_LIMIT_EXCEEDED` and a
`Retry-After` header when the limit is reached. `/health` and `/api/v1/health` are exempt.

Expensive routes use separate buckets: `/api/v1/assistant/chat` (default 10/min/IP) and
`/api/v1/locations/search` / `/api/v1/locations/reverse` (default 20/min/IP) no longer consume
the global 120/min/IP allowance. This limits LLM/geocoding quota abuse without throttling
ordinary air-quality reads.

Client identity is `request.client.host` by default. `X-Forwarded-For` and `X-Real-IP` are
honoured **only** when the immediate peer is listed in `TRUSTED_PROXY_IPS`; otherwise the
headers are ignored because they are trivially spoofable.

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `RATE_LIMIT_STORE` | `memory` | `memory` (zero-config default) or `redis` (opt-in, shared across processes). |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL. May contain credentials; never logged. |
| `REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS` | `0.1` | Bounded connection timeout. |
| `REDIS_SOCKET_TIMEOUT_SECONDS` | `0.2` | Bounded socket read/write timeout. |
| `REDIS_MAX_CONNECTIONS` | `10` | Bound on the async connection pool. |
| `RATE_LIMIT_MAX_REQUESTS` | `120` | Global per-client ceiling per window. |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Fixed-window length in seconds. |
| `RATE_LIMIT_ASSISTANT_REQUESTS` | `10` | Dedicated assistant/chat ceiling. |
| `RATE_LIMIT_LOCATION_REQUESTS` | `20` | Dedicated geocoding ceiling. |
| `TRUSTED_PROXY_IPS` | `[]` | Peers allowed to supply forwarded-IP headers; validate as IP addresses at startup. |

Set these as environment variables (or in the backend-local `.env`). An unknown
`RATE_LIMIT_STORE` raises a startup error rather than silently changing behavior.

The default memory store needs no extra package. For the Redis store, install
`redis` (`pip install -r backend/requirements.txt` includes it). `redis.asyncio` is imported
lazily inside `RedisRateLimitStore.setup()`, so the application never imports Redis when the
memory store is selected.

The middleware still takes `max_requests`, `window_seconds`, optional `path_limits`, and
optional `trusted_proxies` arguments (configured in `backend/app/main.py` from settings). A
custom store can be injected for tests. Keys are `ratelimit:<ip>` for the global bucket and
`ratelimit:<ip>:<path-prefix>` for dedicated buckets.

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

## Redis outage policy: fail-open for cheap reads, local throttle for expensive routes

If the store's `setup` or `check` raises (Redis down, timeout, missing driver, etc.), the
global bucket allows the request and logs a generic warning. This keeps a rate-limiter outage
from becoming a full API outage. For the assistant and location buckets, the middleware falls
back to an in-memory store so a shared-store outage cannot remove the last guard on paid or
quota-limited providers. The log message intentionally excludes the exception details because
driver errors can embed `REDIS_URL` and its password.

## Verification status and tests

Unit tests in `backend/tests/unit/test_security_rate_limit.py` use a fake async Redis client:

- in-memory store still enforces the limit and `reset()` clears it;
- Redis store issues one atomic `eval` per request, uses the Lua `INCR`/`PEXPIRE`/`PTTL`
  script, passes the window as milliseconds, and uses the TTL for `Retry-After`;
- a simulated Redis connection failure results in cheap global requests being allowed
  (fail-open) with no credentials in the logs;
- config selects the expected store, and an unknown store value is rejected.

`backend/tests/unit/test_security_hardening.py` additionally verifies dedicated path buckets,
trusted-proxy handling, the local fallback throttle on an expensive route during a Redis
outage, unsafe CORS/trusted-proxy config rejection, and API security headers.

**Live Redis was not verified in this environment.** No Redis server was started and no
integration test against a real Redis instance was run; the Redis path is validated only with
a fake async client and mocked commands.
