# CPCB / data.gov.in integration

## Scope and evidence policy

This document distinguishes **provider-reported**, **locally verified**, and **unverified** behaviour.

- The resource ID, endpoint, field names, and `3,976` total-record count were supplied by the task owner as a previously observed response.
- During this implementation, live probes from this machine to the resource returned an HTTP 502 after ~61 s and three read timeouts after ~45 s (unfiltered, `filters[state]`, and `filters[city]`). Therefore the total count and filter behaviour are **not independently verified here**.
- A second, deliberately bounded verification pass repeated an unfiltered `limit=1` request with a 12 s read timeout (`ReadTimeout` after 12.6 s), then unfiltered / `filters[state]=Tamil Nadu` / `filters[city]=Chennai` with 8 s read timeouts (`ReadTimeout` after 8.5 s, 8.4 s and 8.5 s respectively). A public data.gov.in metadata page fetch returned HTTP 403. No live response body has ever been observed from this machine.
- Because no live response was observed, the pollutant averaging-period contract cannot be verified. `CPCB_AVERAGING_PERIOD_VERIFIED` therefore remains `false`. A public fetch of CPCB's National Air Quality Index documentation also failed with a transport error, so no external confirmation was obtained either.
- Unit tests use mocked HTTP responses and never require a live key.
- Set `RUN_LIVE_TESTS=1` to opt into the two live integration modules. They are skipped by default in CI. When the provider is reachable, set `CPCB_READ_TIMEOUT_SECONDS` and `CPCB_MAX_RETRIES` to bounded values before running them.

## Resource

| Item | Value |
|---|---|
| Provider | Central Pollution Control Board (CPCB), India |
| Portal | data.gov.in |
| Dataset | Real Time Air Quality Index from Various Locations |
| Resource ID | `3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69` |
| Endpoint | `https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69` |
| Response format | JSON (`format=json`) |
| Authentication | `api-key` query parameter sourced from `DATA_GOV_IN_API_KEY` |

The key is never hardcoded, returned by an API, printed in logs, or exposed to the frontend. `logging.getLogger("httpx")` is raised to `WARNING` because `httpx` INFO logs include the credentialed URL. All adapter error text is passed through `redact_secrets()`.

## Configuration

The existing `backend/app/core/config.py` `Settings` class is the only configuration mechanism. It resolves `.env` from `backend/.env` when present, otherwise from the repository-root `.env`, so the key loads whether uvicorn starts from `backend/` or the repository root.

Add to `.env` (which is gitignored):

```env
DATA_GOV_IN_API_KEY=your_real_key
```

Relevant settings:

| Setting | Default | Purpose |
|---|---:|---|
| `CPCB_PAGE_SIZE` | 100 | `limit` per upstream page |
| `CPCB_MAX_PAGES` | 10 | Hard cap on unfiltered pagination |
| `CPCB_MAX_RETRIES` | 2 | Bounded retries for transient failures |
| `CPCB_BACKOFF_BASE_SECONDS` | 0.5 | Exponential backoff base |
| `CPCB_CONNECT_TIMEOUT_SECONDS` | 5.0 | Explicit connect timeout |
| `CPCB_READ_TIMEOUT_SECONDS` | 20.0 | Explicit read timeout |
| `CPCB_CACHE_TTL_SECONDS` | 300 | Short-TTL provider cache |
| `CPCB_LAST_VALID_MAX_HOURS` | 24 | Bound on stale fallback reuse |
| `CPCB_FRESH_HOURS` | 2 | Fresh threshold (application display rule) |
| `CPCB_DELAYED_HOURS` | 6 | Delayed threshold (application display rule) |
| `CPCB_AVERAGING_PERIOD_VERIFIED` | `false` | Gates official AQI calculation |

Missing key behaviour: production startup of the adapter raises `CPCBConfigurationError`; development logs a warning and disables only the CPCB provider. Other providers continue to work.

## Observed source structure

Fields present in the task-provided sample:

```
country, state, city, station, last_update, latitude, longitude,
pollutant_id, min_value, max_value, avg_value
```

Each row is **one pollutant at one station and one source timestamp**. The adapter groups rows by `(station, city, state, latitude, longitude, last_update)`. Different timestamps are never merged. Exact duplicate pollutant rows are collapsed and a warning is added.

Normalized internal structure (illustrative, not a claim that the provider returns this JSON):

```json
{
  "provider": "CPCB",
  "source": "data.gov.in",
  "state": "Tamil Nadu",
  "city": "Chennai",
  "station": "Station Name",
  "station_id": "cpcb_tamil_nadu_chennai_station_name",
  "latitude": 12.9815,
  "longitude": 80.2182,
  "last_update": "2026-11-25T05:30:00+05:30",
  "retrieval_timestamp": "2026-11-25T06:00:00+00:00",
  "freshness": "verified",
  "pollutants": {
    "PM2.5": {
      "pollutant_id": "PM2.5",
      "min": 10.0,
      "max": 90.0,
      "avg": 45.5,
      "unit": null
    }
  },
  "warnings": []
}
```

### Units

The observed sample has no `pollutant_unit`. The adapter therefore sets `unit = null` unless a record explicitly contains a non-empty unit string. The frontend renders `Unit not provided by source` rather than guessing `µg/m³` or `mg/m³`.

### Timestamps

`last_update` is parsed in this order:

1. `%d-%m-%Y %H:%M:%S`
2. `%Y-%m-%d %H:%M:%S`
3. `%d/%m/%Y %H:%M:%S`
4. ISO-8601

Local-looking timestamps are interpreted as Asia/Kolkata. `retrieval_timestamp` is always UTC and is stored separately from `last_update`.

### Pollutant identifiers

Supported CPCB codes are normalized to `PM2.5`, `PM10`, `NO2`, `SO2`, CO, O3, NH3, and Pb. The original `pollutant_id` is preserved in `source_pollutant_id`. Numeric strings are validated; `NA`, empty strings, malformed values, negatives, NaN, and infinities become `null` rather than zero.

## Filters

Filter values are not trusted. The adapter first fetches a small unfiltered page and extracts exact `state` and `city` strings. A filter is sent upstream only when its value was observed in those records, or when the dedicated probe verified it.

`verify_filters()` independently probes:

- `filters[state] = Tamil Nadu`
- `filters[city] = Chennai`

Each result is classified as one of:

- `verified`
- `value_not_in_sample`
- `no_records`
- `filter_returned_unrelated_records`
- `provider_unavailable`

If a filter is unverified or returns zero records, the adapter falls back to bounded unfiltered pagination followed by exact local filtering. Rows from unrelated cities are never relabelled as Chennai.

**Current verification status:** unverified from this machine. The follow-up probes again timed out for the unfiltered, state and city requests (see the evidence policy above). The task owner reports a prior successful unfiltered response with `3,976` records, but that response was not observed here. Run the opt-in live test and inspect `GET /api/v1/air-quality/filters/verification` on a reachable network to update this status with evidence.

## Pagination and caching

- `_request_page()` uses explicit `limit` and `offset`, bounded retries, and no retry for `400`, `401`, or `403`.
- `429` uses `Retry-After` when numeric, capped at 10 s.
- `500`, `502`, `503`, `504`, timeouts, and transport errors retry with exponential backoff.
- Invalid JSON, non-object payloads, and missing `records` raise safely.
- Duplicate rows are removed by a deterministic record fingerprint.
- Cache TTL defaults to 300 s. Per-key `asyncio.Lock` coalesces concurrent identical fetches.
- On a failed refresh or empty upstream response, the last valid observation is returned with freshness `stale` and a warning, for at most `CPCB_LAST_VALID_MAX_HOURS`. Errors are never cached as valid readings.

## Freshness

Freshness uses the source observation timestamp, not fetch time:

| Source age | Status |
|---|---|
| ≤ 2 h | `verified` |
| > 2 h and ≤ 6 h | `delayed` |
| > 6 h | `stale` |
| Invalid, missing, or future timestamp | `unavailable` |

These are application display thresholds, not official CPCB classifications. The API returns both `last_update` and `retrieval_timestamp`.

## AQI

`backend/app/core/aqi_calculator.py` implements Indian CPCB breakpoints with sub-indices, the ≥3-pollutant rule, and the PM2.5/PM10 requirement. It is not US EPA AQI.

However, the observed dataset exposes pollutant `min`/`max`/`avg`, and its averaging period has not been verified from this machine. Therefore `CPCB_AVERAGING_PERIOD_VERIFIED` defaults to `false` and CPCB-backed observations return:

- `calculated_aqi: null`
- `aqi_category: null`
- `dominant_pollutant: null`
- `data_sufficiency_met: false`
- a note explaining that AQI is unavailable

Do not change the flag to `true` until the deployed feed's averaging-period contract is verified. Pollutant averages are never labelled as AQI.

## Backend endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/air-quality/nearby?lat=&lon=&max_distance_km=` | All CPCB station observations within a radius; distances use haversine great-circle calculation |
| `GET /api/v1/air-quality/summary?city=&state=` | CPCB observations filtered by exact city/state |
| `GET /api/v1/air-quality/station/{station_id}` | One station observation |
| `GET /api/v1/air-quality/filters/verification` | Verified/unverified filter probe status |
| `GET /api/v1/stations` | Live CPCB station metadata; labelled `fallback_registry` only when CPCB is unavailable |

Provider failures return HTTP 503 with a generic detail. No upstream URL or key is included.

## Frontend behaviour

- Station name, city, state, and real station coordinates are displayed.
- Source observation time and server retrieval time are displayed separately.
- Freshness status is shown; stale/delayed/unavailable data gets an explicit warning.
- Units appear only when the provider supplies them.
- Min/max/average are shown as pollutant statistics, not AQI.
- Empty, error, loading, stale, and retry states are distinct.
- Map markers are populated only from live CPCB station metadata. When only the labelled fallback registry is available, the map is hidden instead of plotting guessed city centres.

## Tests

Default, no live network or key required:

```bash
cd backend
.venv/bin/python -m pytest tests/ -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Opt-in live checks:

```bash
cd backend
RUN_LIVE_TESTS=1 DATA_GOV_IN_API_KEY=... .venv/bin/python -m pytest tests/integration -q -m live
```

Frontend:

```bash
cd frontend
npm run test:ci
npm run type-check
npm run build
```

## Known limitations

- Live CPCB availability could not be confirmed from this machine during implementation.
- Chennai/Tamil Nadu filter behaviour is implemented and probed but not verified here.
- Unfiltered pagination is deliberately bounded, so a station outside the first `CPCB_MAX_PAGES * CPCB_PAGE_SIZE` records may not appear.
- The station nearest to a user is a reporting monitor, not a measurement at the user's home. Distance is great-circle, not road distance.
- Official AQI remains unavailable until the averaging-period contract is verified.
- Rate limiting remains in-process, not distributed across multiple backend instances.
