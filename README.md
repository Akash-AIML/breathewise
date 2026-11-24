# BreatheWise — Evidence-Based Urban Air Quality Assistant

> **PromptWars Virtual Challenge 6 — Production-Quality Submission**

[![Backend Tests](https://img.shields.io/badge/Backend%20Tests-65%20passing-brightgreen)](backend/tests)
[![Coverage](https://img.shields.io/badge/Coverage-88%25-brightgreen)](backend)
[![TypeScript](https://img.shields.io/badge/TypeScript-strict-blue)](frontend)
[![WCAG](https://img.shields.io/badge/WCAG-2.2%20AA-blue)](frontend)

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
| CPCB / data.gov.in | Yes (DATA_GOV_IN_API_KEY) | Official Indian NAQI values | Primary |
| OpenAQ v3 | Yes (OPENAQ_API_KEY) | Global station network | Secondary |
| Open-Meteo CAMS | No | ECMWF grid for India | Tertiary (always available) |

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

> **Security:** Never commit `.env`. All AI keys are server-side only. Frontend never receives API keys.

---

## Running Tests

### Backend

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v                              # All 65 tests
coverage run -m pytest tests/ && coverage report  # With coverage (target: 88%)
```

Test categories:
- `tests/unit/` — AQI calculator, policy engine, adapters, API endpoints, AI assistant
- `tests/adversarial/` — stale data, missing pollutants, provider failures
- `tests/integration/` — live Open-Meteo API probe

### Frontend

```bash
cd frontend
npm run type-check   # TypeScript strict mode
npm run test:ci      # Vitest + React Testing Library
npm run build        # Production build (~230kB JS)
```

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
| GET | `/api/v1/stations?city=` | Station registry search |
| GET | `/api/v1/stations/compare?ids=` | Multi-station comparison |
| POST | `/api/v1/recommendations/plan` | Personalized daily plan |
| POST | `/api/v1/recommendations/indoor` | Indoor air guidance + CADR |
| POST | `/api/v1/recommendations/sustainable-alternatives` | Emission alternatives |
| POST | `/api/v1/assistant/chat` | Grounded AI conversational query |

---

## Known Limitations

1. **CPCB API Rate Limits** — data.gov.in demo keys are rate-limited (HTTP 429). The service automatically cascades to OpenAQ → Open-Meteo.
2. **Open-Meteo CAMS Grid Resolution** — CAMS provides ~11km grid estimates, not point-source station readings. It is clearly labelled as a tertiary fallback.
3. **Historical Trends** — 24-hour trend data is available from Open-Meteo CAMS; CPCB historical API requires paid access.
4. **Station Coverage** — 10 major Indian cities are pre-registered. Additional CPCB stations can be added in `backend/app/services/air_quality_service.py`.
5. **Offline LLM** — When no Groq/Gemini API key is configured, the deterministic fallback engine provides complete recommendations without LLM. This is by design.

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
