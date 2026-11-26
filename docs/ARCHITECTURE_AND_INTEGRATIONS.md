# BreatheWise — Architecture, Data Integrations & Deployment

## 1. System Architecture
BreatheWise uses a 3-stage pipeline deployed across two Vercel services (`frontend` Next.js 16 + `backend` FastAPI):
- **Stage 1 (Data Layer):** Cascading live telemetry adapters (`CPCBAdapter` → `OpenAQAdapter` → `OpenMeteoAdapter`) normalized into `NormalizedObservation` with provider provenance, measurement timestamps, and data freshness (`verified`, `estimated`, `delayed`, `stale`, `unavailable`).
- **Stage 2 (Deterministic Risk Engine):** Official CPCB 2014 NAQI linear-interpolation sub-index calculator (`aqi_calculator.py`, requiring ≥3 valid pollutants including PM2.5 or PM10) and deterministic household policy engine (`policy_engine.py`, `policy_plan.py`, `policy_guidance.py`).
- **Stage 3 (Grounded AI Explainer):** Prompt-injection screening (`llm_safety.py`) → Gemini/Groq model failover chain (`llm_providers.py`) → Pydantic validation → deterministic zero-hallucination fallback (`deterministic_assistant.py`).

## 2. CPCB / data.gov.in Integration
- Queries OGD resource `3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69` with circuit breaker (`CPCB_CIRCUIT_BREAKER_SECONDS = 60`), request coalescing, and wall-clock budget (`CPCB_REQUEST_BUDGET_SECONDS = 3.0`).
- Coordinate matching uses Haversine great-circle distance. Station averages without verified 24h CPCB averaging periods are reported without synthetic AQI labels (`CPCB_AVERAGING_PERIOD_VERIFIED = False`).

## 3. LLM Failover & Grounding
- Free-tier Gemini model chain (`gemini-3.1-flash-lite` → `gemini-3.5-flash-lite` → `gemma-4-31b-it` → `gemma-4-26b-a4b-it`) bounded by `LLM_REQUEST_BUDGET_SECONDS = 20.0`.
- If all external LLMs are unconfigured, rate-limited, or fail validation, `generate_deterministic_fallback` synthesizes a grounded response from live station telemetry and approved policy actions.

## 4. Rate Limiting & Vercel Topology
- Sliding-window rate limiter (`core/security.py`) with memory store (default) or Redis (`RATE_LIMIT_STORE=redis`, Lua atomic script) for multi-worker deployments.
- Tighter per-IP limits on `/api/v1/assistant/query` (10 req/min) and `/api/v1/locations/*` (20 req/min), plus global 120 req/min limit.
- Root `vercel.json` defines the `frontend` and `backend` Vercel services; frontend `/api/v1/*` and `/health` route handlers proxy to `BACKEND_URL` at request time.
