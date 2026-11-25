# Station Differential Comparison — Fix and Independent Evaluation

Date: 2026-11-25  
Scope: `Station Differential Comparison` presets, `/api/v1/stations/comparison-presets`, `/api/v1/stations/compare`, frontend preset UI, and the related docs/artifacts. No deployment was attempted.

## 1. Reported problem and evidence

The user reported that comparison presets were “static and not working”.

Evidence before the fix:

- `frontend/src/components/dashboard/station-comparison-view.tsx` defined `PRESET_COMPARISONS` in the browser with hardcoded IDs such as `cpcb_delhi_ito`, `cpcb_delhi_anand_vihar`, `cpcb_mumbai_bandra`, `cpcb_bengaluru_btm`, `cpcb_lucknow_lalbagh`, and `cpcb_kolkata_victoria`.
- The component immediately called `fetchStationComparison(preset.ids)` with those IDs. It did not ask the backend which stations were available and did not receive a provenance/basis field.
- The comparison response had no `basis`, `source`, `requested_ids`, or `unresolved_ids`; the UI could not distinguish a live CPCB station observation from a fallback registry coordinate estimate.
- Local HTTP checks returned `200` for the old hardcoded IDs, with `provider: openmeteo_cams`, `station_id: cpcb_*`, and `distance_km: 0.0`. That is not an HTTP failure, but it is a semantic failure: the response looked like a CPCB station comparison while the data came from the coordinate grid fallback.
- No live CPCB response body was observed in this pass. The hardcoded IDs were therefore not verified as current live CPCB station IDs, and the user-reported `3,976` total remains unconfirmed.

Conclusion: the “static” part of the report is confirmed. The “not working” part was not an endpoint crash locally; it was an availability/provenance failure that could reasonably appear broken or misleading to a user when live station coordinates were absent.

## 2. Root cause

1. The preset catalogue was owned by the frontend instead of being derived from backend station availability.
2. The comparison API had no explicit contract for live station vs fallback coordinate-grid data.
3. Fallback observations retained legacy `cpcb_*` IDs and were presented without an explicit “not a physical station observation” warning.
4. Provider city strings were not normalised, so live presets could disappear if CPCB returned values such as `Bombay`, `Bangalore`, or `Calcutta`.

## 3. Correction applied

Backend:

- Added `GET /api/v1/stations/comparison-presets`.
  - If live CPCB observations resolve, presets are built from those station IDs and reported coordinates, with `basis: live_station` and `source: CPCB/data.gov.in`.
  - If live station coordinates are unavailable, presets are built from `INDIAN_CITIES_REGISTRY` as `grid:<registry_id>` with `basis: coordinate_estimate` and `source: fallback_registry_coordinate_grid`.
- Changed `GET /api/v1/stations/compare` to accept IDs from the preset endpoint and return `basis`, `source`, `requested_ids`, `unresolved_ids`, and an explicit `message`.
- Live IDs are normalised through the existing CPCB adapter. Grid IDs use the existing coordinate air-quality service at the exact registered coordinate, then relabel the result as a grid estimate with provider `fallback_registry_coordinate` and a note that it is **not a physical station observation**.
- Added city/state/label alias matching (`Bombay`, `Bangalore`, `Calcutta`) so live presets do not silently disappear on provider naming variants.
- Added the new route to the API rate-limit map and both proxy allowlists.

Frontend:

- Removed the hardcoded preset catalogue.
- Loads presets from `/api/v1/stations/comparison-presets`, shows a loading state, a reload control, source text, and the backend honesty message.
- Uses `aria-pressed` on preset buttons and `role="status"` / `role="alert"` on status and error blocks.
- Split results rendering into `comparison-results.tsx` so every scoped source file remains under 300 lines.

No estimated city-centre coordinates were plotted on the map, and the previous “live station coordinates unavailable” map policy was not weakened.

## 4. Regression tests added

Backend, in `backend/tests/unit/test_comparison.py`:

- `test_grid_presets_are_labelled_and_data_driven` — fallback presets exist, use `grid:` IDs, and are all `coordinate_estimate`.
- `test_grid_comparison_never_claims_physical_station` — compared observations carry grid labels, grid notes, basis/source, and a differential.
- `test_live_station_presets_use_reported_coordinates` — live observations produce `live_station` presets and CPCB-normalised observations.
- `test_live_presets_tolerate_provider_city_aliases` — provider naming variants still produce all three presets.
- Existing 400-validation tests were retained and updated to the current ID format.

Frontend:

- `src/test/station-comparison-view.test.tsx` — verifies that presets come from the backend, no hardcoded preset name is rendered, and grid estimates are labelled honestly.
- `src/test/security-config.test.ts` — verifies the new proxy route is allowlisted.

All new tests use mocked HTTP/mocked adapters. Default CI does not call a live provider.

## 5. Tests and checks actually executed

| Command | Actual result |
|---|---|
| `cd backend && .venv/bin/ruff check .` | `All checks passed!` |
| `cd backend && .venv/bin/ruff format --check .` | `70 files already formatted` |
| `cd backend && .venv/bin/pytest tests/ -q` | **158 passed, 2 skipped**, 4 Starlette deprecation warnings; no failures |
| `cd backend && .venv/bin/python -m coverage run -m pytest tests/ -q` | **158 passed, 2 skipped** |
| `cd backend && .venv/bin/python -m coverage report --include='app/*' -m` | **2324 statements, 306 missed, 87%** |
| `cd backend && .venv/bin/python -m coverage xml/html` | `coverage.xml` **151,594 B**; HTML regenerated |
| `cd backend && .venv/bin/python -m pip_audit -r requirements.txt` | `No known vulnerabilities found` |
| `cd frontend && npm run test:ci` | **62 passed / 16 files**, 0 failed |
| `cd frontend && npm run type-check` | clean (`tsc --noEmit`) |
| `cd frontend && npm run build` | Next.js 16.4.6 build passed; TypeScript passed; 3 static pages generated |
| `cd frontend && npm audit --json` | `{"info":0,"low":0,"moderate":0,"high":0,"critical":0,"total":0}` |
| Scoped source line count | Largest `.py/.ts/.tsx` file is **297 lines**; no scoped file exceeds 300 |
| Secret scan | 3 configured real key values checked across 171 tracked/local artifacts: **0 hits** |

Local smoke after the final backend restart:

| Check | Actual result |
|---|---|
| `GET /api/v1/stations/comparison-presets` | **200 in 3.06s**; `source=fallback_registry_coordinate_grid`; keys `delhi-corridors`, `metro-cross-city`, `indo-gangetic-plain` |
| `GET /api/v1/stations/compare?station_ids=grid:cpcb_delhi_ito,grid:cpcb_delhi_anand_vihar` | **200 in 4.16s**; `basis=coordinate_estimate`; 2 observations; AQI `[224, 224]` |
| Frontend `/` | **200 in 0.07s** |
| Presets through Next proxy | **200 in 3.04s**; 3 presets; fallback source |
| Compare through Next proxy | **200 in 0.01s**; `basis=coordinate_estimate`; all observations carried the grid note |

Earlier in this pass, a three-city fallback comparison returned AQI `[220, 136, 42]` with `basis=coordinate_estimate`; the AQI difference between smoke runs reflects refreshed CAMS data, not a code change. No live CPCB response was observed.

## 6. Six-parameter assessment

| Parameter | Assessment | Evidence / caveat |
|---|---|---|
| CODE QUALITY | **Pass** | Single backend service/schema/endpoint owns the comparison contract; frontend preset catalogue deleted; results component split; ruff and TypeScript clean; largest scoped file 297 lines. The presets endpoint and compare endpoint still share one module-level service instance, which is intentional for cache reuse but couples their test patching. |
| SECURITY | **Pass with unchanged caveats** | New route is explicitly proxied and rate-limited; no credential was added; fresh 3-key/171-file scan found 0 hits; redaction and existing allowlists remain. The CPCB key remains in the provider query string because the provider requires it; the paid LLM route still lacks authenticated user identity. |
| EFFICIENCY | **Pass with timing caveat** | No unbounded calls were added; CPCB lookup failures remain circuit-broken and grid coordinate results use existing caching. Local preset resolution took 3.06s because live CPCB still times out before fallback; compare took 4.16s with two grid coordinates. The Next first-load bundle was not re-measured after this UI split. |
| TESTING | **Pass** | Backend 158 passed/2 skipped, frontend 62 passed, app coverage 87%, both dependency audits clean, new regressions cover live/fallback/alias/label behaviour. Mocked tests do not prove live CPCB schema compatibility. |
| ACCESSIBILITY | **Pass for covered states; no fresh Lighthouse** | Preset buttons expose `aria-pressed`; status and error regions use roles; axe checks in `npm run test:ci` regenerated `axe-results.json` with 0 violations for covered states. Lighthouse was not rerun. |
| PROBLEM ALIGNMENT | **Pass for the reported preset defect; partial overall** | Presets are now data-driven and honestly labelled; exact registered coordinates are preserved; fallback observations are never presented as physical stations. Deployment, live CPCB, Chennai/Tamil Nadu filters, averaging-period verification, and production performance remain unverified. Grid AQI is computed with official CPCB methodology from CAMS rolling averages, not measured at a CPCB station. |

## 7. Devil’s advocate findings

- The old endpoint returned HTTP 200 locally, so the user’s “not working” complaint is not reproduced as an exception. The confirmed defect is semantic and availability-driven. If the product requirement is “only live CPCB station comparisons”, even honestly labelled grid estimates should be disabled instead of shown.
- Live CPCB was not observed, so `live_station` preset construction is verified only with mocked CPCB-shaped observations. A different real schema could still yield zero live presets and fall back to grid estimates.
- Fallback grid comparisons compare two model estimates at registered coordinates. They are useful for relative regional context but cannot support a claim about a specific monitoring station’s reading.
- The preset response is fetched on component mount, and the first comparison is triggered immediately. On a slow CPCB timeout this delays first useful content by roughly 3 seconds locally.
- `loadPresets` and the mount effect contain similar fetch/error logic; this is a maintainability smell even though the component is under 300 lines.
- The `grid:` IDs are an internal contract. If a future client hardcodes them again, the backend will still resolve them, so the UI fix depends on continued discipline, not an API-level prohibition.
- Coverage rose to 87%, but that percentage does not prove the fallback labels match every real provider payload.

## 8. Remaining issues

1. No deployment credentials or URL; `docs/DEPLOYMENT_STATUS.md` remains a blocker record.
2. Live CPCB reachability, the `3,976` record count, Chennai/Tamil Nadu filters, and averaging-period verification remain unconfirmed.
3. Production Lighthouse/bundle measurements are stale; no fresh run after this UI split.
4. Redis is unit-tested with a fake client only; no live Redis verification.
5. The paid LLM route still has no authenticated user identity.
6. Proxy-collapsed client IP requires correct `TRUSTED_PROXY_IPS` on any future deployment.

## 9. Next milestone

1. Commit and push this fix, then verify the remote branch is clean.
2. If real CPCB access becomes available, verify the response schema, station coordinates, filters, and averaging period; enable `live_station` presets only from that evidence.
3. Add a capability flag or user preference to hide grid estimates entirely when the requirement is strictly live-station-only comparison.
4. Deploy with platform secrets, HTTPS CORS origins, and trusted proxy configuration; rerun axe/Lighthouse and measure production latency and bundle cost.
