# Security hardening report — key handling and endpoint abuse

Date: 2026-11-25
Scope: BreatheWise backend and frontend, on top of pushed commit `31b4ad7`.
Decision implemented: **harden key handling and endpoint abuse controls; do not add custom
application-level encryption.** Secrets remain server-side configuration values. Custom
encryption would still require a decrypting key in process memory and would add key-rotation
complexity without reducing the abuse surface that was actually observed.

No live deployment was performed and no deployment URL exists. All "live" checks below are
against local backend/frontend servers started from this workspace.

---

## 1. Changed files

### Backend
- `backend/app/core/redaction.py` (new) — central configured-secret and credential-pattern redaction for logs and error details.
- `backend/app/core/security.py` — path-specific rate-limit buckets, trusted-proxy handling, Redis fallback throttle, security headers, `no-store` on `/api/`.
- `backend/app/core/cache.py` (new) — bounded/pruned TTL caches and lock maps.
- `backend/app/core/config.py` — rate-limit/cache/page-size settings plus validation of CORS and trusted-proxy values.
- `backend/app/main.py` — installs redaction, redacts `HTTPException` detail, wires path limits and trusted proxies, narrows CORS request headers.
- `backend/app/adapters/cpcb_transport.py` — bounded CPCB caches and per-key locks.
- `backend/app/services/air_quality_service.py` — bounded exact-coordinate cache.
- `backend/app/api/v1/endpoints/locations.py` — per-key reverse-geocode locks, bounded caches, narrowed geocoding fields.
- `backend/app/api/v1/endpoints/cpcb.py` and `backend/app/api/v1/endpoints/stations.py` — server-enforced list page caps.
- `backend/tests/unit/test_security_hardening.py` (new), `backend/tests/unit/test_api_pagination.py` (new) — regressions for the findings below.

### Frontend and configuration
- `frontend/next.config.js`, `frontend/vercel.json` — explicit API rewrite allowlists instead of wildcard proxying; CSP and security headers.
- `frontend/src/lib/api.ts` — 15s request timeout, safe error messages, production same-origin API base, no production `bypass_cache`.
- `frontend/src/components/assistant/assistant-api.ts` — 25s assistant timeout with headroom over the 20s backend model-chain budget.
- `frontend/src/test/security-config.test.ts` (new), `frontend/src/test/api.test.ts`, `frontend/src/test/setup.ts` — frontend regressions.
- `frontend/package.json`, `frontend/package-lock.json`, `frontend/next-env.d.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.tsbuildinfo` — dependency upgrade and Next 16 generated TypeScript settings.
- `.env.example`, `.gitignore`, `README.md`, `docs/RATE_LIMITING.md`, `docs/LLM_FAILOVER.md`, `docs/artifacts/*` — documentation and refreshed evidence.

---

## 2. Functionality delivered

- API keys are read only by backend `Settings`; no key is sent to the browser and no client-side configuration can redirect API traffic to a third-party origin in production.
- Logs, tracebacks, and user-visible HTTP exception details are sanitised using the currently configured secret values plus generic query/header/bearer/Redis-credential patterns.
- Rate limiting now has separate buckets for assistant and geocoding routes, honours forwarded headers only from configured proxy peers, and retains a local throttle for expensive routes if a shared Redis store fails.
- All user-controlled caches and lock maps are bounded; all list endpoints now have a server-enforced ceiling (`API_MAX_PAGE_SIZE=500`).
- Browser-facing API rewrites are explicit allowlists; CORS rejects wildcard and production non-HTTPS origins; page and API responses carry defence-in-depth headers.
- Frontend failures show fixed safe text, and requests are aborted with explicit timeouts.

---

## 3. Findings, corrections, and regression evidence

| ID | Failure observed / risk | Severity | Root cause | Correction | Regression test | Re-run check |
|---|---|---|---|---|---|---|
| F1 | A provider exception, traceback, or `HTTPException.detail` could include a configured key, an `api-key=` URL, a bearer token, or Redis credentials. | High | No single sanitisation boundary existed; provider libraries format credentials into exception text. | `SecretRedactionFilter` installed on application/uvicorn/httpx handlers in `main.py`; `redact_text()` applied to HTTP error details. | `test_redaction_removes_configured_and_pattern_secrets`, `test_logging_filter_redacts_message_and_traceback`, `test_http_error_detail_is_redacted`. | Full backend suite passed; fresh scan of 10 local log/response artifacts with 3 configured keys found **0 leaks** and never printed a key. |
| F2 | `X-Forwarded-For`/`X-Real-IP` could choose a rate-limit bucket; expensive LLM/geocoding routes shared the global bucket; Redis failure removed all throttling. | High | Client-controlled headers were trusted and one counter covered every route. | Trusted-proxy allowlist, longest-prefix path buckets, and in-memory fallback for expensive routes only. | `test_forwarded_ip_header_is_trusted_only_from_configured_proxy`, `test_expensive_routes_use_separate_rate_limit_buckets`, `test_redis_outage_still_throttles_expensive_route`, `test_security_settings_reject_unsafe_configuration`. | Full backend suite passed; unit test verifies a Redis outage still yields `200,200,429` and logs no URL/password. |
| F3 | Attacker-controlled coordinate/city keys could grow caches and per-key lock maps without limit. | Medium | Plain `dict`/`defaultdict` caches with TTL but no entry cap. | `prune_expired`, `enforce_limit`, `bound_locks` helpers; applied to air-quality, CPCB, and reverse-geocode state. | `test_air_quality_cache_is_bounded_and_expires_entries`, `test_cpcb_per_key_locks_are_bounded`. | Full backend suite passed; caches evict FIFO to configured caps and expired entries are removed on read. |
| F4 | Station/CPCB list endpoints could return an unbounded number of records. | Medium | No `limit` parameter or server-side ceiling despite provider pagination. | `API_MAX_PAGE_SIZE=500`; explicit `limit` on `/stations`, `/air-quality/summary`, and `/air-quality/nearby`. | `test_stations_list_enforces_page_size`, `test_cpcb_list_endpoints_enforce_page_size`. | Live local check: `stations?limit=3` → `count=3`, `stations?limit=501` → **422**; full backend suite passed. |
| F5 | CORS could be wildcard/non-HTTPS in production, and Next/Vercel rewrites could expose unintended backend routes. | Medium | Permissive defaults and wildcard proxy patterns. | Settings validation rejects `*` and production HTTP origins; CORS request headers narrowed; explicit rewrite allowlists in Next and Vercel; production ignores remote `NEXT_PUBLIC_API_BASE_URL`. | `test_security_settings_reject_unsafe_configuration`, `frontend/src/test/security-config.test.ts`. | Full suites passed. Live check: `Origin: https://evil.example` produced **no** `Access-Control-Allow-Origin`; `http://localhost:3000` was allowed. |
| F6 | Raw upstream error text could reach the UI, and slow requests could hang indefinitely. | Medium | Frontend rendered thrown response text; fetch had no timeout; assistant timeout exactly matched the backend budget. | `safeErrorMessage()` with fixed user text; `AbortController` timeouts; assistant timeout raised to 25s for 5s headroom over the 20s backend chain. | `frontend/src/test/api.test.ts`, `frontend/src/test/security-config.test.ts`. | Frontend 62/62 passed; through the Next proxy, assistant returned **200 in 8.25s** with `llm_grounded: true`, AQI 220, provenance `openmeteo_cams`. |
| F7 | npm audit reported 8 advisories including critical/high dev-tooling issues. | High | Outdated `next`, `vitest`, `vite`, and `@vitejs/plugin-react`. | Upgraded to `next@16.4.6`, `vitest@5.1.1`, `vite@7.x`, `@vitejs/plugin-react@5.2.0`. | Existing suite plus new security-config tests. | `npm audit --json` → **0 total vulnerabilities**; 62 tests, type-check, and production build all pass. |
| F8 | `.env` hygiene was not enforced against accidental commits. | Medium | Local secret file and broad env patterns were not fully ignored. | `.gitignore` now ignores `.env.*` except `.env.example`, plus key/certificate files; `.env` mode set to `600`; `.env.example` documents safe defaults. | Repository secret audit (historical) plus fresh artifact scan. | Earlier audit: **0 real secrets** in 159 tracked files, 12 commits, 284 reachable blobs, 61 unreachable blobs, docs/artifacts, and video artifacts. `.env` remains untracked and was never committed. |
| F9 | Security headers were incomplete/inconsistent between backend API and frontend pages. | Medium | No central header policy; API responses could be stored by shared caches. | Backend `SecurityHeadersMiddleware` and frontend `headers()` both set X-Frame-Options, Referrer-Policy, Permissions-Policy, COOP/CORP, nosniff; API adds `Cache-Control: no-store`; CSP added on pages. | `test_security_headers_set_page_and_api_policies`. | Live header checks confirmed CSP on `/`, and `no-store` plus COOP/CORP/X-Permitted on a real API response. |
| F10 | The first live failover chat took **19.47s**, only 0.53s inside the previous 20s browser timeout. | Low–Medium | Frontend assistant deadline equalled the backend `LLM_REQUEST_BUDGET_SECONDS` with no network/proxy margin. | Assistant timeout raised to 25s; `docs/LLM_FAILOVER.md` and README updated. | No separate numeric timeout test; covered by full frontend suite and live proxy smoke. | Direct backend chat succeeded with `gemini-3.5-flash-lite`; subsequent rebuilt frontend proxy chat returned **200 in 8.25s**. |

No application-level encryption/decryption was added. The provider-required CPCB `api-key` query parameter is still used on the server-to-server request, but it is never logged, returned to the client, or exposed in frontend code, and is covered by redaction if it appears in diagnostic text.

---

## 4. Tests and checks executed

| Command | Actual result |
|---|---|
| `cd backend && .venv/bin/ruff check .` | `All checks passed!` |
| `cd backend && .venv/bin/ruff format --check .` | `70 files already formatted` |
| `cd backend && .venv/bin/python -m coverage run -m pytest tests/ -q` | **158 passed, 2 skipped**, 4 Starlette deprecation warnings; no failures |
| `cd backend && .venv/bin/python -m coverage report --include='app/*' -m` | **2324 statements, 306 missed, 87%** |
| `cd backend && .venv/bin/python -m coverage xml/html` | `coverage.xml` (151,594 B) and `coverage-html/index.html` regenerated |
| `cd backend && .venv/bin/python -m pip_audit -r requirements.txt` | `No known vulnerabilities found` |
| `cd frontend && npm run test:ci` | **62 passed / 16 files**, 0 failed; axe results regenerated |
| `cd frontend && npm run type-check` | clean (`tsc --noEmit`) |
| `cd frontend && npm run build` | Next.js 16.4.6 Turbopack build passed: compiled, TypeScript passed, 3 static pages generated |
| `cd frontend && npm audit --json` | `{"info":0,"low":0,"moderate":0,"high":0,"critical":0,"total":0}` |
| `find backend/app frontend/src ... wc -l` | Largest scoped source file is 297 lines; no scoped file exceeds 300 lines |
| Backend/frontend live smoke | health 200; frontend `/` 200; air quality 200 in 4.97s; assistant 200 in 19.47s direct and 8.25s through proxy; reverse 200 in 0.36s; stations limit 200/422 as expected |
| Exact-coordinate check | `28.6322,77.2422` → provider `openmeteo_cams`, AQI 220, station coordinates equal request, `distance_km 0.0` |
| Tier-2 label check | `11.4953,77.2793` → `Sathyamangalam, Tamil Nadu (OpenStreetMap Nominatim)`; no Bengaluru mislabel |
| Grounding check | Assistant `llm_grounded: true`, AQI 220, risk `high`, provenance `openmeteo_cams`; log names only `gemini-3.1-flash-lite` / `gemini-3.5-flash-lite`, never a key |
| Secret scan | 3 configured keys checked against 10 fresh log/response artifacts → **0 leaks** |

Live tests remain opt-in (`RUN_LIVE_TESTS=1`) and are not part of default CI. No live CPCB response was observed in this hardening pass.

---

## 5. Six-parameter assessment

| Parameter | Assessment | Evidence / caveat |
|---|---|---|
| CODE QUALITY | **Pass** | One config system and one client/adapter per provider; new concerns separated into `redaction.py`, `cache.py`, and focused test modules; ruff lint/format clean; largest scoped source file 297 lines. Facades/re-exports still add one level of indirection. |
| SECURITY | **Pass with documented caveats** | Redaction, trusted-proxy rate limiting, dedicated expensive-route buckets, Redis fallback throttle, bounded caches/pages, validated CORS, explicit rewrites, CSP/headers, 0 npm/pip advisories, 0 secret leaks in fresh artifacts. The paid LLM route still has no authenticated user identity; it is protected by 10/min/IP plus a local fallback and safe output handling. |
| EFFICIENCY | **Pass with a bundle caveat** | No new outbound calls; CPCB provider is briefly skipped after failure; bounded caches prevent memory growth; local in-process p95 remains ~1 ms from the existing artifact. Next 16 `/` first-load JS measured **975,893 B raw / 269,865 B gzip**, up from the earlier 241 kB Next 15 figure, so this pass is not a bundle-size improvement. Browser Lighthouse was not re-run after the security changes. |
| TESTING | **Pass** | Backend 158 passed / 2 skipped, frontend 62 passed, app coverage 87%, type-check/build clean, both dependency audits clean, new tests cover each high/medium finding. Coverage does not prove live provider fidelity. |
| ACCESSIBILITY | **No regression; fresh axe evidence** | `npm run test:ci` includes axe checks and regenerated `axe-results.json` with 0 violations for the covered states. The older Lighthouse accessibility 100 was dev-mode and one page state; no fresh Lighthouse run after this pass. |
| PROBLEM ALIGNMENT | **Partial, unchanged external blockers** | Exact coordinates, grounded assistant, safe defaults, and honest provenance survived the hardening. Deployment, live CPCB confirmation, Chennai/Tamil Nadu filter verification, CPCB averaging-period verification, and production performance remain unverified. |

---

## 6. Remaining issues

1. **No deployment.** No Render/Vercel credentials, CLI login, or deployment URL exists; `docs/DEPLOYMENT_STATUS.md` remains a blocker record.
2. **Live CPCB remains unreachable.** Bounded probes timed out; no live response body was observed. The user-reported `3,976` total remains unconfirmed.
3. **Filters and averaging period unverified.** Chennai/Tamil Nadu filter verification is not established; `CPCB_AVERAGING_PERIOD_VERIFIED=false`, so CPCB AQI stays unavailable rather than mislabelled.
4. **Proxy-collapsed client identity.** If `TRUSTED_PROXY_IPS` is not set correctly on the deployment platform, all clients behind one proxy share one bucket. The setting is validated but not live-tested with a real Redis/proxy deployment.
5. **Redis store is unit-tested with a fake client only.** No live Redis instance was available; production should monitor store errors and alert on the generic fallback warning.
6. **No authenticated LLM user identity.** Rate limiting is per IP plus dedicated route buckets; a shared NAT or an attacker rotating IPs can still consume quota. Auth/quotas are out of scope for this pass but remain a real risk.
7. **CPCB `api-key` is in the provider query string** because the provider requires it. It is redacted in diagnostics and never exposed to the browser; TLS at the provider boundary must be preserved.
8. **Lighthouse is stale.** The stored Lighthouse run is dev-server evidence (performance 74, accessibility 100, best practices 96, SEO 100) and should be repeated against a deployment.
9. **Bundle size regressed.** The Next 16 first-load gzip size is ~270 kB versus the earlier 241 kB figure; no code-splitting work was done in this phase.
10. **`health` still reports provider configuration flags** (`configured` / `unconfigured_degraded`). No key value is exposed, but this is low-severity reconnaissance information.

---

## 7. Devil's advocate findings

- The redaction filter is last-line defence, not prevention. A future code path that deliberately writes a secret to a file, metrics label, or third-party sink bypasses it.
- Exact-value redaction depends on settings loaded in the same process. A key injected only into a provider subprocess or sidecar would not be in `_configured_secrets()`; pattern rules are the fallback and are not exhaustive.
- Rate-limit tests use a recording store and a fake Redis client. They prove middleware decisions, not Redis Lua behaviour under real concurrency.
- Page caps bound response size but change semantics: `count` is now the number returned on the page, not the total matching set. Callers needing totals require a future pagination contract with an explicit `total`.
- The 19.47s direct assistant response proves failover worked, but it also shows a second model was needed. A successful 8.25s retry does not establish model availability or a latency SLA.
- The fresh secret scan checked configured values in local artifacts only; it does not replace rotation if the workstation was shared before `.env` was chmod'ed to `600`.
- App coverage returned to 87% after adding the comparison regressions; coverage percentage remains a weak proxy for provider fidelity. The new tests cover the new security behaviour explicitly.
- No custom encryption means the threat model explicitly accepts that a compromised backend process with configuration access can read keys. That is deliberate; app-level crypto would not change this unless keys were externally managed.

---

## 8. Next milestone

1. Commit this hardening pass and verify the remote branch is clean.
2. Deploy backend and frontend only when platform credentials are available; set production CORS HTTPS origins, `TRUSTED_PROXY_IPS`, and secrets through platform secret stores.
3. Repeat Lighthouse and axe against the deployed origin, then measure real production latency and bundle cost.
4. Obtain a live CPCB response and independently verify filters, averaging period, and record count before enabling any CPCB-derived AQI.
5. Add authenticated user quotas or an API gateway if the LLM route becomes publicly scalable beyond per-IP controls.
