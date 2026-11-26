# BreatheWise — Evidence-Based Urban Air Quality Assistant

[![Backend Quality](https://github.com/Akash-AIML/breathewise/actions/workflows/ci.yml/badge.svg)](https://github.com/Akash-AIML/breathewise/actions/workflows/ci.yml)

BreatheWise helps Indian families navigate urban air pollution using verified telemetry (CPCB/data.gov.in, OpenAQ, Open-Meteo CAMS), a deterministic CPCB 2014 NAQI & household policy engine, and a grounded multi-turn AI assistant.

> **Fabrication policy:** BreatheWise never generates synthetic AQI values. If all providers fail, it displays an honest unavailable state.

## Architecture

```
Frontend (Next.js 16, TypeScript, Tailwind)
  └── /api/v1/* & /health proxy ──▶ Backend (FastAPI, Python 3.12+)
                                      ├── Stage 1: CPCB → OpenAQ → Open-Meteo adapters
                                      ├── Stage 2: CPCB NAQI calculator & Policy engine
                                      └── Stage 3: Injection screen → Gemini/Groq → Deterministic fallback
```

## Quick Start

### 1. Environment
Copy `.env.example` to `.env` and set optional API keys (`DATA_GOV_IN_API_KEY`, `OPENAQ_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`).

### 2. Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000`.

## Running Tests & Quality Checks

```bash
# Backend
cd backend && source .venv/bin/activate
ruff check . && ruff format --check . && mypy app/ && bandit -r app/ -ll
coverage run -m pytest tests/ && coverage report --fail-under=80

# Frontend
cd frontend
npx tsc --noEmit && npm run lint && npm run test:ci
```

## Documentation
- [Architecture, Integrations & Deployment](docs/ARCHITECTURE_AND_INTEGRATIONS.md)
- [Security, Code Quality & Testing](docs/SECURITY_AND_QUALITY.md)
- [Features & Problem Statement Alignment](docs/FEATURES_AND_ALIGNMENT.md)
