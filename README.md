# BreatheWise — Evidence-Based Urban Air Quality Assistant

> **PromptWars Virtual Challenge 6 — Production-Quality Submission**
>
> Public repository: https://github.com/Akash-AIML/breathewise — **not deployed**; see
> [`docs/DEPLOYMENT_STATUS.md`](docs/DEPLOYMENT_STATUS.md).

[![Backend Tests](https://img.shields.io/badge/Backend%20Tests-136%20passing-brightgreen)](backend/tests)
[![Frontend Tests](https://img.shields.io/badge/Frontend%20Tests-54%20passing-brightgreen)](frontend/src/test)
[![Coverage](https://img.shields.io/badge/Coverage-85%25-yellow)](docs/artifacts/coverage-html/index.html)
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
- **Exact coordinates plus a readable place label** — “Use My Location” shows the device coordinates and a reverse-geocoded locality (OpenStreetMap Nominatim) as a label only; queries still use the exact coordinates. When reverse geocoding is unavailable, a popular-station label is used only within 25 km; distant cities are never reported as “near”.
- **Personalized household recommendations** — deterministic policy engine tuned to your household's vulnerabilities
- **Low-emission daily routines** — diurnal planning with temperature inversion and ozone dispersion modelling
- **Indoor air quality guidance** — CADR calculator, filter maintenance, cooking smoke management
- **Sustainable alternatives** — documented Indian ARAI/CEA emission factors
- **Explainable AI recommendations** — Groq/Gemini LLM explains pre-approved deterministic outputs only
- **Transparent impact assessments** — provider provenance, measurement timestamps, data freshness clearly displayed

> **Fabrication policy:** BreatheWise never generates synthetic AQI values. If all providers fail, it shows an honest unavailable state.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                     Next.js Frontend (Vercel)                      │
│  Tabs: Dashboard | Planner | Indoor | Sustainability | Trends |    │
│         Comparison | Map | AI Assistant                            │
└───────────────────────────────┬────────────────────────────────────┘
                                │ HTTPS (rewrites via vercel.json)
┌───────────────────────────────▼────────────────────────────────────┐
│                   FastAPI Backend (Render.com)                      │
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

> The platform names in this diagram are **configuration targets**, not live deployments. No Render
> or Vercel deployment was performed here; see [`docs/DEPLOYMENT_STATUS.md`](docs/DEPLOYMENT_STATUS.md).

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
# Edit BACKEND_URL in next.config.js if backend is not on localhost:8000
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
| `CORS_ORIGINS` | Yes (prod) | JSON array of allowed frontend origins |
| `ENVIRONMENT` | No | `development` or `production` |
| `CACHE_TTL_SECONDS` | No | Observation cache TTL (default: 900s) |
| `BACKEND_URL` | Frontend | URL of backend for Next.js rewrites |

The complete list of CPCB pagination, timeout, freshness and cache settings is in
[`docs/CPCB_INTEGRATION.md`](docs/CPCB_INTEGRATION.md); rate-limit store settings are in
[`docs/RATE_LIMITING.md`](docs/RATE_LIMITING.md).

> **Security:** Never commit `.env`. All AI keys are server-side only. Frontend never receives API keys.

---

## Running Tests

### Backend

```bash
cd backend
source .venv/bin/activate
pytest tests/ -q     # 136 passed, 2 live tests skipped by default
RUN_LIVE_TESTS=1 pytest tests/integration -q -m live   # opt-in; requires network + keys
coverage run -m pytest tests/ -q && coverage report --include='app/*'  # app code: 85%
```

Test categories:
- `tests/unit/` — AQI calculator, policy engine, adapters, API endpoints, AI assistant, CPCB integration, rate-limit stores, geocoding proxy
- `tests/adversarial/` — stale data, missing pollutants, provider failures
- `tests/integration/` — opt-in live CPCB and Open-Meteo probes (`RUN_LIVE_TESTS=1`)

### Frontend

```bash
cd frontend
npm run type-check   # TypeScript strict mode
npm run test:ci      # Vitest + React Testing Library + axe; 54 passed
npm run build        # Production build; First Load JS 240 kB
```

All provider tests use mocked HTTP by default. Live tests are opt-in and are **not** part of CI.

---

## Deployment

### Backend (Render.com)

1. Connect your GitHub repository to Render
2. Create a new **Web Service** pointing to `backend/`
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Set environment variables in Render dashboard
6. The `backend/render.yaml` configures this automatically for IaC deployment

### Frontend (Vercel)

1. Import repository to Vercel
2. Set **Root Directory** to `frontend`
3. Add environment variable: `BACKEND_URL=https://your-render-service.onrender.com`
4. Deploy — `frontend/vercel.json` handles API proxy rewrites

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
| GET | `/api/v1/stations/compare?ids=` | Multi-station comparison |
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

