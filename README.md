# BreatheWise — Evidence-Based Urban Air Quality Assistant

> **PromptWars Virtual Challenge 6 — Production-Quality Submission**
>
> Public repository: https://github.com/Akash-AIML/breathewise — deployment performed from the
> browser; no deployment was created from this environment. See
> [`docs/DEPLOYMENT_STATUS.md`](docs/DEPLOYMENT_STATUS.md).

[![Backend Tests](https://img.shields.io/badge/Backend%20Tests-158%20passing-brightgreen)](backend/tests)
[![Frontend Tests](https://img.shields.io/badge/Frontend%20Tests-78%20passing-brightgreen)](frontend/src/test)
[![Coverage](https://img.shields.io/badge/Coverage-87%25-yellow)](docs/artifacts/coverage-html/index.html)
[![TypeScript](https://img.shields.io/badge/TypeScript-strict-blue)](frontend)
[![axe](https://img.shields.io/badge/axe-0%20violations-brightgreen)](docs/artifacts/axe-results.json)

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Modules](#modules)
4. [Data Sources](#data-sources)
5. [Getting Started](#getting-started)
6. [Environment Variables](#environment-variables)
7. [Running Tests](#running-tests)
8. [Deployment](#deployment)
9. [API Documentation](#api-documentation)
10. [Known Limitations](#known-limitations)
11. [AI Integration Principles](#ai-integration-principles)

---

## Project Overview

BreatheWise helps Indian families navigate urban air pollution through:

- **Genuine real-time air quality measurements** — CPCB/data.gov.in, OpenAQ, Open-Meteo CAMS (cascading failover)
- **Location-aware station selection** — 10+ verified Indian CPCB stations with Haversine distance calculation
- **Exact coordinates plus a readable place label** — “Use My Location” requests a fresh high-accuracy device fix (`maximumAge: 0`), shows the reported coordinates and accuracy radius, and uses a reverse-geocoded locality (OpenStreetMap Nominatim) as a label only; queries still use the device coordinates. Invalid fixes and browser-reported accuracy worse than ±2 km are rejected rather than being labelled exact, so laptop IP/Wi-Fi fallbacks do not silently replace your location. A manual `lat, lon` input is available when a laptop browser reports the wrong point. When reverse geocoding is unavailable, a popular-station label is used only within 25 km; distant cities are never reported as “near”.
- **Personalized household recommendations** — deterministic policy engine tuned to your household's vulnerabilities
- **Low-emission daily routines** — diurnal planning with temperature inversion and ozone dispersion modelling
- **Indoor air quality guidance** — CADR calculator, filter maintenance, cooking smoke management
- **Sustainable alternatives** — documented Indian ARAI/CEA emission factors
- **Explainable AI recommendations** — free-tier Gemini model chain explains pre-approved deterministic outputs only, with automatic failover and a deterministic fallback when every model is unavailable
- **Transparent impact assessments** — provider provenance, measurement timestamps, data freshness clearly displayed

> **Fabrication policy:** BreatheWise never generates synthetic AQI values. If all providers fail, it shows an honest unavailable state.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│              Vercel project · frontend service (public)            │
│  Tabs: Dashboard | Planner | Indoor | Sustainability | Trends |    │
│         Comparison | Map | AI Assistant                            │
│  /api/v1/* and /health → request-time route handlers                │
└───────────────────────────────┬────────────────────────────────────┘
                                │ service binding BACKEND_URL (internal, runtime)
┌───────────────────────────────▼────────────────────────────────────┐
│                Vercel project · backend service (FastAPI)           │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Stage 1: Data Layer (Adapters)                             │   │
│  │  CPCB Adapter → OpenAQ Adapter → Open-Meteo Adapter        │   │
│  │  NormalizedObservation schema (provider, timestamp, unit)   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Stage 2: Risk Engine (Deterministic)                       │   │
│  │  CPCB NAQI Calculator → Policy Engine → Recommendation Sets │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Stage 3: AI Explainer (Narration Only)                     │   │
│  │  Prompt Injection Screen → Groq/Gemini → Pydantic Validate  │   │
│  │  → Deterministic Fallback (zero-failure path)               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

**Core Principle:** The LLM is restricted to narrating approved, deterministic outputs. It never calculates risk or invents measurements.

> This Vercel Services topology is a **configuration target**, not a live deployment. The root
> `vercel.json` defines both services, and `backend/render.yaml` remains an alternative Render
> blueprint. Neither was deployed here; see [`docs/DEPLOYMENT_STATUS.md`](docs/DEPLOYMENT_STATUS.md).

---

## Modules

| Module | Tab | Description |
|--------|-----|-------------|
| Air Quality Dashboard | Live Dashboard | Real-time AQI, pollutant breakdown, provenance, freshness |
| Station Explorer | Station Map | SVG India map with 10 CPCB station pins, keyboard-navigable |
| Station Comparison | Station Comparison | Side-by-side multi-station differential analysis |
| 24-Hour Trends | 24-Hour Trends | Recharts area chart with accessible HTML table alternative |
| Household Profile | (Dialog) | Optional vulnerability and lifestyle settings |
| Daily Planner | Daily Planner | Morning/afternoon/evening personalized action cards |
| Indoor Air Guide | Indoor Air Guide | CADR calculator, filter maintenance, cooking precautions |
| Sustainable Transit | Sustainable Transit | ARAI/CEA emission factor comparisons |
| AI Assistant | AI Assistant | Grounded conversational Q&A with quick prompt chips |

---

## Data Sources

| Provider | Key Required | Coverage | Fallback Priority |
|----------|-------------|----------|-----------------|
| CPCB / data.gov.in | Yes (DATA_GOV_IN_API_KEY) | Station-reported pollutant min/max/avg; official AQI only when averaging is verified | Primary |
| OpenAQ v3 | Yes (OPENAQ_API_KEY) | Global station network | Secondary |
| Open-Meteo CAMS | No | ECMWF grid for India | Tertiary (always available) |

See [`docs/CPCB_INTEGRATION.md`](docs/CPCB_INTEGRATION.md) for the resource schema, verified/unverified filter status, caching, freshness, and AQI limitations.

---

## Getting Started

### Prerequisites

- Python ≥ 3.11
- Node.js ≥ 18
- (Optional) PostgreSQL — not required for current in-memory caching tier

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env          # Edit with your API keys
uvicorn app.main:app --reload --port 8000
```

Health check: http://localhost:8000/health

### Frontend

```bash
cd frontend
npm install
# BACKEND_URL is read by the request-time proxy handlers. For plain next dev,
# export it here or put it in frontend/.env.local; Vercel injects it instead.
export BACKEND_URL=http://127.0.0.1:8000
npm run dev
```

App: http://localhost:3000

---

## Environment Variables

Copy `.env.example` to `.env` in the project root (or `backend/`):

| Variable | Required | Description |
|----------|----------|-------------|
| `DATA_GOV_IN_API_KEY` | No | CPCB data.gov.in API key (apply at https://data.gov.in) |
| `OPENAQ_API_KEY` | No | OpenAQ v3 API key (register at https://explore.openaq.org) |
| `GROQ_API_KEY` | No | Groq LLM API key (https://console.groq.com) |
| `GEMINI_API_KEY` | No | Google Gemini API key (https://ai.google.dev) |
| `GEMINI_MODELS` | No | Ordered free-tier model failover chain (default: Gemini 3.1 Flash Lite → Gemini 3.5 Flash Lite → Gemma 4 31B → Gemma 4 26B) |
| `LLM_REQUEST_BUDGET_SECONDS` | No | Wall-clock ceiling for the whole chain (default: 20s; frontend allows 25s) |
| `GEMINI_MODEL_TIMEOUT_SECONDS` / `GEMMA_MODEL_TIMEOUT_SECONDS` | No | Per-model read timeouts (default: 10s / 12s) |
| `CORS_ORIGINS` | Yes (prod) | JSON array of allowed frontend origins; wildcard and non-HTTPS production origins are rejected |
| `RATE_LIMIT_MAX_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` | No | Global per-IP limit (default: 120 / 60s) |
| `RATE_LIMIT_ASSISTANT_REQUESTS` / `RATE_LIMIT_LOCATION_REQUESTS` | No | Dedicated expensive-route limits (default: 10 / 20 per minute) |
| `TRUSTED_PROXY_IPS` | No | JSON array of proxy peers allowed to supply forwarded-IP headers (default: `[]`) |
| `CACHE_MAX_ENTRIES` / `CPCB_MAX_LOCKS` | No | Bounds for attacker-controlled cache keys and per-key locks |
| `ENVIRONMENT` | No | `development` or `production` |
| `CACHE_TTL_SECONDS` | No | Observation cache TTL (default: 900s) |
| `BACKEND_URL` | Frontend (local) | Backend base URL read at request time by the Next.js proxy handlers. On Vercel this is injected by the `backend` service binding; do not set it manually there. |

The complete list of CPCB pagination, timeout, freshness and cache settings is in
[`docs/CPCB_INTEGRATION.md`](docs/CPCB_INTEGRATION.md); rate-limit store settings are in
[`docs/RATE_LIMITING.md`](docs/RATE_LIMITING.md).

> **Security:** Never commit `.env`. All AI keys are server-side only. Frontend never receives API keys.
> Logs and HTTP error details are sanitised with configured-secret redaction; `chmod 600 .env`
> is recommended for local workstations. See [`docs/SECURITY_HARDENING_REPORT.md`](docs/SECURITY_HARDENING_REPORT.md).

---

## Running Tests

### Backend

```bash
cd backend
source .venv/bin/activate
pytest tests/ -q     # 158 passed, 2 live tests skipped by default
RUN_LIVE_TESTS=1 pytest tests/integration -q -m live   # opt-in; requires network + keys
coverage run -m pytest tests/ -q && coverage report --include='app/*'  # app code: 87%
```

Test categories:
- `tests/unit/` — AQI calculator, policy engine, adapters, API endpoints, AI assistant, CPCB integration, rate-limit stores, geocoding proxy
- `tests/adversarial/` — stale data, missing pollutants, provider failures
- `tests/integration/` — opt-in live CPCB and Open-Meteo probes (`RUN_LIVE_TESTS=1`)

### Frontend

```bash
cd frontend
npm run type-check   # TypeScript strict mode
npm run test:ci      # Vitest + React Testing Library + axe; 72 passed
npm run build        # Next 16 production build; / first-load JS diagnostics: 975,893 B raw / 269,865 B gzip
```

All provider tests use mocked HTTP by default. Live tests are opt-in and are **not** part of CI.

---

## Deployment

### Vercel Services (repository root)

The root [`vercel.json`](vercel.json) defines two services in one project:

- `backend` — FastAPI service rooted at `backend/`, internal only.
- `frontend` — Next.js service rooted at `frontend/`, the only public service.

The frontend declares a service binding to the backend as `BACKEND_URL`. Vercel injects that URL into the Next.js route handlers at runtime; do **not** set `BACKEND_URL` manually in the Vercel dashboard. Browser requests stay same-origin (`/api/v1/*`, `/health`) and are proxied by request-time route handlers that read the binding.

To deploy:

1. Import the GitHub repository into Vercel with **Root Directory** set to the repository root.
2. Select the **Services** framework preset (CLI: `vercel project update --framework services`).
3. Set `ENVIRONMENT=production` and `CORS_ORIGINS` to the HTTPS deployment origin(s). Provider keys remain optional server-side secrets.
4. Do not set `BACKEND_URL` or `NEXT_PUBLIC_API_BASE_URL` in Vercel.
5. Deploy. Preview deployments receive a preview-scoped backend binding automatically.
6. Test locally with `vercel dev` (or `vercel dev --local`) so the binding is injected the same way.

See [`docs/VERCEL_SERVICES.md`](docs/VERCEL_SERVICES.md) for the routing contract and environment-variable checklist. Configuration is prepared here; no deployment has been executed from this environment.

### Backend (Render.com template)

`backend/render.yaml` remains an alternative Render web-service blueprint. It is not used by the Vercel Services deployment.

### Docker (Backend)

```bash
cd backend
docker build -t breathewise-backend .
docker run -p 8000:8000 --env-file .env breathewise-backend
```

---

## API Documentation

Interactive docs available at: `http://localhost:8000/docs`

Key endpoints:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health and version |
| GET | `/api/v1/air-quality?lat=&lon=` | Real-time observation for coordinates |
| GET | `/api/v1/air-quality/nearby?lat=&lon=` | Individual CPCB station observations with haversine distance |
| GET | `/api/v1/air-quality/summary?city=&state=` | CPCB observations by exact city/state |
| GET | `/api/v1/air-quality/station/{station_id}` | One CPCB station observation |
| GET | `/api/v1/air-quality/filters/verification` | Verified/unverified Chennai and Tamil Nadu filter probes |
| GET | `/api/v1/stations?city=` | Live CPCB station search with labelled fallback |
| GET | `/api/v1/locations/search?name=` | Same-origin geocoding proxy |
| GET | `/api/v1/locations/reverse?lat=&lon=` | Cached, rate-limited reverse geocoding (Nominatim) |
| GET | `/api/v1/stations/comparison-presets` | Data-driven comparison presets from live stations, or labelled coordinate-grid estimates |
| GET | `/api/v1/stations/compare?station_ids=` | Multi-station comparison; IDs come from `/comparison-presets` |
| POST | `/api/v1/recommendations/plan` | Personalized daily plan |
| POST | `/api/v1/recommendations/indoor` | Indoor air guidance + CADR |
| POST | `/api/v1/recommendations/sustainable-alternatives` | Emission alternatives |
| POST | `/api/v1/assistant/chat` | Grounded AI conversational query |

---

## Known Limitations

1. **CPCB provider reachability** — live data.gov.in probes from the development machine timed out or returned 502. A per-request budget and circuit breaker limit the stall to ~3 s before the app falls back to OpenAQ → Open-Meteo. See [`docs/CPCB_INTEGRATION.md`](docs/CPCB_INTEGRATION.md).
2. **CPCB AQI** — the dataset's averaging period is not verified here, so CPCB-backed responses show pollutant concentrations with AQI unavailable instead of inventing an official index.
3. **Filter verification** — Chennai/Tamil Nadu filters are probed at runtime and documented as verified only after a successful response.
4. **Open-Meteo CAMS Grid Resolution** — CAMS provides ~11km grid estimates, not point-source station readings. It is clearly labelled as a tertiary fallback.
5. **Historical Trends** — 24-hour trend data is available from Open-Meteo CAMS; CPCB historical API requires paid access.
6. **Station Coverage** — unfiltered CPCB pagination is bounded. A labelled static registry is used only when live station metadata is unavailable.
7. **Offline LLM** — When no Groq/Gemini API key is configured, the deterministic fallback engine provides complete recommendations without LLM. This is by design.
8. **Distributed rate limiting** — the in-memory default is per-process. An opt-in Redis store (`RATE_LIMIT_STORE=redis`) shares counters across instances and fails open on store errors; no live Redis instance was tested here. See [`docs/RATE_LIMITING.md`](docs/RATE_LIMITING.md).
9. **Comparison presets** — when live CPCB station coordinates are unavailable, presets compare exact registered coordinates through the grid provider and are explicitly labelled `coordinate_estimate`. They are not physical CPCB station observations. See [`docs/STATION_COMPARISON_FIX_REPORT.md`](docs/STATION_COMPARISON_FIX_REPORT.md).

---

## Verification evidence

Everything below was measured locally; none of it implies a live provider success or a deployment.

| Artifact | What it shows |
|---|---|
| [`docs/PHASE_2_CPCB_REPORT.md`](docs/PHASE_2_CPCB_REPORT.md) | Phase 1 precision fixes and CPCB adapter implementation |
| [`docs/MILESTONE_3_REPORT.md`](docs/MILESTONE_3_REPORT.md) | Audits, shared rate limiting, live-test attempt, publication |
| [`docs/CPCB_INTEGRATION.md`](docs/CPCB_INTEGRATION.md) | Schema, config, filter-verification status (unverified) and probe evidence |
| [`docs/artifacts/README.md`](docs/artifacts/README.md) | Index of raw audit output, coverage, performance and demo files |
| [`docs/artifacts/axe-results.json`](docs/artifacts/axe-results.json) | axe: HomePage 21 rules / 0 violations, profile dialog 20 rules / 0 violations |
| [`docs/artifacts/lighthouse.json`](docs/artifacts/lighthouse.json) | Local dev-server Lighthouse: performance 74, accessibility 100, best practices 96, SEO 100 |
| [`docs/artifacts/npm-audit.json`](docs/artifacts/npm-audit.json) | 8 unresolved dev-tooling vulnerabilities (4 moderate, 2 high, 2 critical) |
| [`docs/artifacts/pip-audit.txt`](docs/artifacts/pip-audit.txt) | `No known vulnerabilities found` for backend requirements |
| [`docs/artifacts/performance.json`](docs/artifacts/performance.json) | 140 serial in-process ASGI requests: p50 0.668 ms, p95 1.038 ms |
| [`docs/artifacts/breathewise-demo.mp4`](docs/artifacts/breathewise-demo.mp4) | 37.2 s real screen capture of the local verification instance |
| [`docs/LINKEDIN_PROCESS.md`](docs/LINKEDIN_PROCESS.md) | Process write-up based only on measured work |

---

## AI Integration Principles

BreatheWise follows a strict **three-stage grounded AI architecture**:

| Stage | Component | Allowed To Do |
|-------|-----------|---------------|
| 1 | Data Adapters + CPCB NAQI Calculator | Fetch real data, compute official AQI |
| 2 | Policy Engine | Deterministic risk classification and recommendation generation |
| 3 | LLM Explainer | Narrate Stage 1+2 outputs in natural language |

**The LLM is NEVER permitted to:**
- Calculate or modify AQI values
- Fabricate pollutant readings or station names
- Override risk classifications
- Recommend actions outside the Stage 2 approved set
- Respond to prompt injection attempts

If the LLM produces malformed output, schema validation rejects it and the deterministic fallback engine responds instantly.

