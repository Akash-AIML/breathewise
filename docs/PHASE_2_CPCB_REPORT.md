# Phase 2 report — CPCB/data.gov.in integration and precision fixes

Date: 2026-11-25. Status: **implemented and locally verified; live provider and deployment NOT verified**.

## Evidence policy

This report records only commands actually run in this workspace. Live provider claims are
limited to the probes described below. No passing result, deployment, or filter behaviour is
asserted without evidence.

---

## 1. Changed files

### Backend — CPCB adapter and schemas
- `backend/app/adapters/cpcb.py` — async httpx client, redacted logging, bounded retries/backoff, pagination, verified-filter logic, grouping by station + source timestamp, freshness, cache/coalescing, stale fallback, nearby discovery, AQI gate.
- `backend/app/schemas/cpcb.py` — CPCB row/observation/filter schemas (new).
- `backend/app/core/geo.py` — haversine distance helper (new).
- `backend/app/schemas/observation.py` — nullable `unit`, `min_value`/`max_value`/`source_pollutant_id`, station `provider`/`source_observation_time`, `DELAYED` status.
- `backend/app/core/config.py` — backend-local or repo-root `.env` resolution; 11 CPCB settings.

### Backend — API and security
- `backend/app/api/v1/endpoints/cpcb.py` — nearby, summary, station, filter-verification endpoints (new).
- `backend/app/api/v1/endpoints/stations.py` — prefers live CPCB stations; labelled `fallback_registry` otherwise.
- `backend/app/api/v1/endpoints/locations.py` — same-origin geocoding proxy (new).
- `backend/app/api/v1/router.py` — registers CPCB and locations routers.
- `backend/app/api/v1/endpoints/recommendations.py`, `assistant.py` — `Cache-Control: no-store` on profile-derived responses.
- `backend/app/services/llm_assistant_service.py` — Unicode/homoglyph-normalized injection screening, structural control-token detection, output-side control-token rejection.

### Frontend
- `src/app/page.tsx` — CPCB provenance, real station identity/coordinates, source vs retrieval time, min/max/avg, unit fallback, stale/delayed warning, retry, honest empty state, live-only map markers, ARIA tablist with arrow/Home/End keys.
- `src/lib/api.ts` — station lat/lon params, same-origin geocoding proxy, error-body messages.
- `src/types/observation.ts` — `delayed`, nullable unit/averaging, min/max/source fields, station provenance, stations message.
- `src/components/dashboard/historical-trend-chart.tsx` — missing values shown as `—` instead of fabricated zero; honest source labelling; accessible toggle pressed state.
- `src/components/profile/household-profile-dialog.tsx` — focus trap, Escape-to-close, focus restoration, `aria-describedby`.
- New tests: `api.test.ts`, `page-location.test.tsx`, `cpcb-observation.test.tsx`, `tabs-accessibility.test.tsx`.

### Docs/config
- `docs/CPCB_INTEGRATION.md` (new), `docs/PHASE_2_CPCB_REPORT.md` (this file), `.env.example`, `README.md`.

---

## 2. Functionality

1. **Precise coordinates** flow from geolocation/search into observation and plan requests; station selection no longer substitutes a city centre for a user location.
2. **CPCB adapter** uses the actual documented fields (`state`, `city`, `station`, `last_update`, `latitude`, `longitude`, `pollutant_id`, `min_value`, `max_value`, `avg_value`), validates coordinates and timestamps, normalizes pollutant IDs, groups by station + timestamp, and never invents units.
3. **Filters** are verified against a live unfiltered sample before being sent upstream; unverified or zero-result filters fall back to bounded unfiltered pagination plus exact local filtering.
4. **Freshness** uses source time: ≤2h verified, 2–6h delayed, >6h stale, invalid/future/missing unavailable. Failed refresh preserves the last valid observation and marks it stale.
5. **AQI** remains unavailable for CPCB data unless `CPCB_AVERAGING_PERIOD_VERIFIED=true`; concentrations are still displayed with min/max/avg.
6. **API** exposes CPCB-specific endpoints and a `fallback_registry`-labelled station list; geocoding is proxied server-side; profile-derived responses are `no-store`.
7. **Frontend** distinguishes empty/error/stale/loading states, offers retry, hides the map when only estimated fallback coordinates exist, and implements WAI-ARIA tablist and modal patterns.

---

## 3. Tests executed and actual results

All commands were run from the stated directory.

| Command | Actual result |
|---|---|
| `cd backend && .venv/bin/ruff check .` | `All checks passed!` |
| `cd backend && .venv/bin/ruff format --check .` | `49 files already formatted` |
| `cd backend && .venv/bin/python -m pytest tests/ -q` | `122 passed, 2 skipped, 2 warnings in 5.09s` (2 live tests skipped by default) |
| `cd backend && .venv/bin/python -m coverage run -m pytest tests/ -q && ... coverage report --include='app/*' -m` | `TOTAL 1723 stmts, 252 missed, 85%` |
| `cd frontend && npm run test:ci` | `Test Files 12 passed (12); Tests 45 passed (45)` |
| `cd frontend && npm run type-check` | clean (`tsc --noEmit`, no output) |
| `cd frontend && npm run build` | clean; route `/` 137 kB, First Load JS 240 kB |
| Bounded live CPCB probe (unfiltered, `limit=1`, explicit 5s connect / 12s read timeout) | `status: transport_error elapsed_seconds: 12.6 error_type: ReadTimeout` |

The two remaining warnings are Starlette deprecation notices for `HTTP_422_UNPROCESSABLE_ENTITY`, not test failures.

Default tests mock HTTP and clear provider/LLM keys in `backend/tests/conftest.py`; live provider tests require `RUN_LIVE_TESTS=1`.

---

## 4. Six-parameter assessment

| Parameter | Assessment | Evidence / caveat |
|---|---|---|
| **Code quality** | Good | Single config schema, single adapter, typed Pydantic schemas, ruff clean, 85% app coverage. Some modules remain large (`llm_assistant_service.py`, `cpcb.py`), acknowledged below. |
| **Security** | Good with caveats | Key server-side only, redaction, no retry on 400/401/403, no credentialed URLs in responses/logs, normalized injection screening, output clamping, `no-store` on profile-derived responses. Rate limiting is still in-process only; no authenticated user accounts. |
| **Efficiency** | Good | Async httpx with explicit timeouts, bounded retries with backoff, pagination cap, per-key cache + request coalescing, stale fallback instead of hard failure, 300s default CPCB TTL. Unfiltered pagination is bounded, so coverage is intentionally partial. |
| **Testing** | Good | 122 backend + 45 frontend passing, mocked HTTP for all provider paths, opt-in live tests, regressions for retries, pagination, filters, freshness, redaction, endpoints, tablist, modal, and chart null handling. No live success is claimed. |
| **Accessibility** | Improved, not audited by axe/Lighthouse | ARIA tablist with keyboard navigation, labelled tabpanels, modal focus trap/Escape/restoration, accessible chart table toggle with `aria-pressed`, explicit empty/error/stale roles. No automated WCAG audit artifact exists. |
| **Problem alignment** | Partial | Precise coordinates, honest provenance, and real CPCB schema handling are implemented. Full alignment is blocked by an unreachable live provider, unverified Chennai/Tamil Nadu filters, unverified averaging period, and absence of deployment/repo/video/audit artifacts. |

---

## 5. Remaining issues

1. **Live CPCB unreachable from this machine** — 502 after ~61s and multiple read timeouts (45s, 12.6s). No successful live response was observed, so the reported `3,976 total records` remains the task owner's observation, not independently confirmed.
2. **Chennai/Tamil Nadu filters unverified** — verification logic is implemented and unit-tested; runtime status must be read from `GET /api/v1/air-quality/filters/verification` on a reachable network.
3. **AQI unavailable for CPCB** — averaging period not verified; flag deliberately false.
4. **Static registry** still seeds the default station and supplies an explicitly labelled fallback; it is never presented as live CPCB data.
5. **In-process rate limiting** is not distributed across multiple backend instances.
6. **No automated accessibility/performance/security audit artifacts**, no axe/Lighthouse run, no saved coverage file, no deployment URL, no public GitHub remote, no demo video, no LinkedIn process document.
7. Chart test output includes Recharts `width(0)/height(0)` warnings in jsdom; behaviour is unaffected but the warning is noise.
8. Starlette 422 deprecation warnings remain (2 warnings).

---

## 6. Devil's advocate findings

- **"You verified the CPCB integration."** No. Only mocked HTTP was verified. Every live probe from this machine failed. The adapter is correct against the supplied schema but its real-world behaviour is unproven here.
- **"The nearest station means pollution at the user's home."** No. It is a reporting monitor's location; distance is great-circle, and the map is hidden when only guessed coordinates exist.
- **"AQI is computed from CPCB averages."** No. Averaging period is unverified; `calculated_aqi` is `null` for CPCB observations by design.
- **"Units are µg/m³."** No. The observed schema has no unit field; the UI explicitly says the unit was not provided.
- **"Accessibility is WCAG 2.2 AA compliant."** Not proven. Patterns were improved but no audit tool was run; the README badge is an aspiration, not evidence.
- **"Coverage 85% means correctness."** No. Coverage measures executed lines, not provider fidelity or live availability.
- **"The app is deployed."** No. Only local verification servers were started and stopped; no deployment exists.
- **"Geocoding is now independent of third parties."** No. It is proxied through our backend but still relies on Open-Meteo upstream.

---

## 7. Next milestone

1. On a network that can reach data.gov.in, run `RUN_LIVE_TESTS=1` live tests and record actual response shape, total count, and Chennai/Tamil Nadu filter statuses; update `docs/CPCB_INTEGRATION.md` from `unverified` to evidence-backed values.
2. Verify the feed's pollutant averaging-period contract; only then consider enabling `CPCB_AVERAGING_PERIOD_VERIFIED` and re-running AQI regressions.
3. Produce real audit artifacts: `axe`/Lighthouse accessibility report, performance timing measurements, dependency/security audit output, and a saved coverage XML/HTML report.
4. Resolve in-process rate limiting with a shared store before multi-instance deployment.
5. Publish a public GitHub repository, deploy backend + frontend, record the demo video, and write the LinkedIn process document.
