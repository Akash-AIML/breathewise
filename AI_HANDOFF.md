# BreatheWise — AI Model Handoff & Continuation Guide

> **Purpose:** If your current AI quota runs out mid-session, use this document to seamlessly resume work in a fresh AI session with any model (Claude, Gemini, GPT-4, Mistral, etc.). This guide contains the full context, architecture decisions, file map, and exact next steps.

---

## 1. Project Identity

| Field | Value |
|-------|-------|
| **Project Name** | BreatheWise — Evidence-Based Urban Air Quality Assistant |
| **Challenge** | PromptWars Virtual Challenge 6 |
| **Working Directory** | `/home/akash/Projects/AirQuality` |
| **Git Branch** | `main` |
| **Backend** | FastAPI + Python 3.12 at `/home/akash/Projects/AirQuality/backend/` |
| **Frontend** | Next.js 15 + TypeScript at `/home/akash/Projects/AirQuality/frontend/` |
| **Backend Virtualenv** | `/home/akash/Projects/AirQuality/backend/.venv` |

---

## 2. What Has Been Completed

### Phase 1 — Data & CPCB Engine
- `backend/app/schemas/observation.py` — Pydantic v2 `NormalizedObservation`, `StationMetadata`, `PollutantType`, `AQICategory`, `DataQualityStatus`
- `backend/app/core/aqi_calculator.py` — Deterministic CPCB 2014 NAQI linear interpolation (8 criteria pollutants, ≥3 sufficiency rule)
- `backend/app/adapters/cpcb.py` — CPCB/data.gov.in adapter
- `backend/app/adapters/openaq.py` — OpenAQ v3 adapter
- `backend/app/adapters/openmeteo.py` — Open-Meteo CAMS adapter (always-available fallback)
- `backend/app/services/air_quality_service.py` — Orchestrator with TTL cache, stale detection, Haversine station distance

### Phase 2 — Backend Foundation & Security
- `backend/app/main.py` — FastAPI app with security headers middleware, CORS, rate limiting
- `backend/app/core/security.py` — CSP headers + sliding window IP rate limiter (120 req/min)
- `backend/app/api/v1/` — REST endpoints: `/health`, `/api/v1/air-quality`, `/api/v1/stations`
- `frontend/` — Next.js 15, Tailwind CSS, shadcn/ui design system: `Button`, `Card`, `Badge`, `AQIBadge`, `Navbar`, `Footer`, `SkipLink`

### Phase 3 — Dashboard & Station Explorer
- `backend/app/api/v1/endpoints/comparison.py` — Multi-station comparison endpoint
- `frontend/src/components/dashboard/historical-trend-chart.tsx` — Recharts 24h area chart + accessible HTML table
- `frontend/src/components/dashboard/station-comparison-view.tsx` — Side-by-side station comparison
- `frontend/src/components/dashboard/station-map.tsx` — Accessible SVG India map with keyboard navigation

### Phase 4 — Personalization & Policy Engine
- `backend/app/schemas/profile.py` — `HouseholdProfile` (children, elderly, respiratory, cardiac, commute, exercise, purifiers, home_area_sqft)
- `backend/app/schemas/recommendation.py` — `EnvironmentalAssessment`, `PersonalizedPlan`, `IndoorGuidance`, `SustainableAlternative`
- `backend/app/core/policy_engine.py` — Deterministic 3-stage policy engine:
  - Risk classification (LOW/MODERATE/HIGH/VERY_HIGH/SEVERE/HAZARDOUS)
  - Diurnal planner (morning inversions, afternoon ozone, evening traffic spikes)
  - HEPA CADR calculator (`Area_sqft × 1.16 m³/hr` for 5 ACH)
  - Houseplant disclaimer (Waring et al. 2019)
  - ARAI/CEA emission factors (Indian transport standards)
- `backend/app/api/v1/endpoints/recommendations.py` — `/recommendations/plan`, `/recommendations/indoor`, `/recommendations/sustainable-alternatives`
- Frontend: `household-profile-dialog.tsx`, `daily-planner.tsx`, `indoor-assistant.tsx`, `sustainable-alternatives.tsx`

### Phase 5 — Explainable AI Assistant ✅ JUST COMPLETED
- `backend/app/schemas/assistant.py` — `ChatQueryRequest`, `ExplanationResponse`
- `backend/app/services/llm_assistant_service.py` — Prompt injection screen, Groq/Gemini structured JSON, Pydantic validation, deterministic fallback
- `backend/app/api/v1/endpoints/assistant.py` — `POST /api/v1/assistant/chat`
- `backend/app/api/v1/router.py` — Updated to include assistant router
- `frontend/src/components/assistant/chat-assistant.tsx` — Full chat UI with quick prompts, grounding badges, risk levels, ARIA attributes
- `frontend/src/app/page.tsx` — AI Assistant tab added (8th tab)
- `backend/tests/unit/test_ai_assistant.py` — 26 tests (injection detection, deterministic fallback, LLM failure modes, schema validation)

### Phase 6 — Deployment Infrastructure
- `backend/Dockerfile` — Production Docker image (non-root user, health check)
- `backend/render.yaml` — Render.com IaC deployment config
- `frontend/vercel.json` — Vercel deployment with API proxy rewrites
- `frontend/next.config.js` — Updated with `/api/*` and `/health` proxy rewrites to backend

### Phase 7 — Documentation
- `README.md` — Comprehensive project README (architecture diagram, API docs, known limitations)

---

## 3. Current Test Status

| Suite | Tests | Status | Coverage |
|-------|-------|--------|----------|
| Backend (Pytest) | 65 | ✅ All Passing | 88% |
| Frontend (Vitest) | 33 | ✅ All Passing | — |
| TypeScript | — | ✅ No errors | — |

---

## 4. File Map

```
AirQuality/
├── README.md                               # Project documentation
├── .env.example                            # Template (no real secrets)
├── .github/workflows/ci.yml               # CI pipeline
│
├── backend/
│   ├── Dockerfile                          # Production container
│   ├── render.yaml                         # Render.com deployment
│   ├── requirements.txt
│   ├── pyproject.toml                      # Ruff + pytest config
│   ├── app/
│   │   ├── main.py                         # FastAPI app entrypoint
│   │   ├── core/
│   │   │   ├── aqi_calculator.py           # CPCB NAQI deterministic engine
│   │   │   ├── config.py                   # Pydantic settings
│   │   │   ├── policy_engine.py            # Risk + recommendation engine
│   │   │   └── security.py                 # Headers + rate limiter
│   │   ├── adapters/
│   │   │   ├── cpcb.py                     # CPCB/data.gov.in
│   │   │   ├── openaq.py                   # OpenAQ v3
│   │   │   └── openmeteo.py               # Open-Meteo CAMS (no key needed)
│   │   ├── schemas/
│   │   │   ├── observation.py              # NormalizedObservation, StationMetadata
│   │   │   ├── profile.py                  # HouseholdProfile
│   │   │   ├── recommendation.py           # PersonalizedPlan, IndoorGuidance
│   │   │   ├── assistant.py                # ChatQueryRequest, ExplanationResponse
│   │   │   ├── comparison.py               # StationComparison
│   │   │   └── api.py                      # Response envelopes
│   │   ├── services/
│   │   │   ├── air_quality_service.py      # Orchestrator with caching
│   │   │   └── llm_assistant_service.py    # Groq/Gemini + fallback engine
│   │   └── api/v1/
│   │       ├── router.py                   # Main router aggregator
│   │       └── endpoints/
│   │           ├── health.py
│   │           ├── air_quality.py
│   │           ├── stations.py
│   │           ├── comparison.py
│   │           ├── recommendations.py
│   │           └── assistant.py            # POST /api/v1/assistant/chat
│   └── tests/
│       ├── unit/                           # 60 unit tests
│       ├── adversarial/                    # 4 adversarial tests
│       └── integration/                    # 1 live API test
│
└── frontend/
    ├── vercel.json                         # Vercel deployment config
    ├── next.config.js                      # Rewrites + security headers
    ├── package.json
    └── src/
        ├── app/
        │   └── page.tsx                    # Main page (8 tabs)
        ├── components/
        │   ├── ui/                         # Button, Card, Badge, etc.
        │   ├── aqi/                        # AQIBadge
        │   ├── dashboard/                  # TrendChart, StationMap, Comparison
        │   ├── profile/                    # HouseholdProfileDialog
        │   ├── planner/                    # DailyPlanner
        │   ├── indoor/                     # IndoorAssistant
        │   ├── sustainability/             # SustainableAlternatives
        │   └── assistant/                  # ChatAssistant ← NEW
        ├── lib/
        │   ├── api.ts                      # fetchAirQuality, fetchPersonalizedPlan
        │   └── utils.ts
        ├── types/
        │   ├── observation.ts
        │   └── recommendations.ts
        └── test/
            ├── setup.ts                    # ResizeObserver + scrollIntoView polyfills
            ├── button.test.tsx
            ├── aqi-badge.test.tsx
            ├── household-profile-dialog.test.tsx
            ├── daily-planner.test.tsx
            ├── indoor-assistant.test.tsx
            └── chat-assistant.test.tsx     # NEW — 13 tests
```

---

## 5. Architecture Principles (Never Violate These)

1. **LLM never calculates risk.** The LLM only explains Stage 1 & 2 outputs.
2. **Never fabricate AQI.** If all providers fail → show honest unavailable state.
3. **Never display stale data as current.** Freshness threshold: 6 hours.
4. **Houseplants cannot replace HEPA filters.** This is explicitly stated (Waring et al. 2019).
5. **Cycling during AQI > 200 increases inhalation exposure by 300–500%.** Active cycling is NOT recommended during severe pollution — only zero-emission transit with N95.
6. **Data sufficiency rule.** NAQI requires ≥3 criteria pollutants, at least one must be PM2.5 or PM10.

---

## 6. If You Are Continuing This Project

### Quick Verification Before Any Work

```bash
# 1. Check tests still pass
cd /home/akash/Projects/AirQuality/backend
source .venv/bin/activate
pytest tests/ -q   # Must show 65 passed

# 2. Check git status
git status         # Clean working tree = safe to continue
git log --oneline -5

# 3. Check frontend type safety
cd /home/akash/Projects/AirQuality/frontend
npm run type-check  # Must show no errors
```

### Remaining Optional Improvements

If the core evaluation is done, these are enhancement opportunities:

| Item | Priority | File |
|------|----------|------|
| Playwright E2E tests | Medium | `frontend/tests/e2e/` |
| axe-core accessibility audit in CI | Medium | `.github/workflows/ci.yml` |
| WebSocket live updates (avoid polling) | Low | `backend/app/api/v1/endpoints/live.py` |
| PostgreSQL caching for CPCB history | Low | `backend/app/db/` |
| Lighthouse CI budget | Low | `.github/workflows/ci.yml` |

---

## 7. AI Model Configuration Guide

### Option A: Groq (Fastest, Recommended)

1. Register at https://console.groq.com
2. Create an API key
3. Add to `.env`: `GROQ_API_KEY=gsk_...`
4. Model used: `llama-3.3-70b-versatile`

### Option B: Google Gemini

1. Get key at https://ai.google.dev
2. Add to `.env`: `GEMINI_API_KEY=AIza...`
3. Model used: `gemini-1.5-flash`

### Option C: No AI Key (Deterministic Fallback)

**The application works fully without any LLM key.** The deterministic fallback engine in `backend/app/services/llm_assistant_service.py` handles all 5 query categories:
- Exercise / outdoor workouts
- Children / school safety
- Houseplants / indoor purification
- Commute / mask usage
- General air quality questions

The only difference is `llm_grounded: false` in responses instead of `true`.

---

## 8. Switching AI Models (In-Code)

To add a new LLM provider (e.g. Mistral, OpenAI, Anthropic):

1. Open `backend/app/services/llm_assistant_service.py`
2. Add a new method: `async def _call_<provider>(self, query, system_prompt, obs, assessment)`
3. Follow the same pattern as `_call_groq()`:
   - POST to provider API with the pre-built `system_prompt` and `query`
   - Parse JSON response
   - **Always** override `referenced_aqi`, `dominant_pollutant`, `risk_level` from the deterministic assessment (never from LLM)
   - Set `llm_grounded=True`
4. Add provider check in `_call_server_llm()` with its API key setting in `backend/app/core/config.py`

**Security constraint:** Never let the LLM's response override Stage 1 or Stage 2 values.

---

## 9. Evaluation Checklist

| Parameter | Status | Evidence |
|-----------|--------|---------|
| Code Quality | ✅ | Modular adapters/services/schemas, Ruff/Black clean, no dead code |
| Security | ✅ | Server-side keys, CORS, rate limiting, CSP, prompt injection screen |
| Efficiency | ✅ | TTL cache, async httpx, exponential backoff, lazy tab loading |
| Testing | ✅ | 65 backend tests, 88% coverage, 33 frontend tests, adversarial cases |
| Accessibility | ✅ | ARIA roles, sr-only labels, keyboard nav, non-color AQI badges, focus rings |
| Problem Alignment | ✅ | All 10 problem statement requirements implemented |
