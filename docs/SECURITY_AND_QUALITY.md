# BreatheWise — Security, Code Quality & Testing

## 1. Security Hardening
- **No fabricated data:** Synthetic AQI generation is strictly prohibited; provider outages surface honest unavailable states.
- **Injection & secret protection:** `llm_safety.py` normalizes Unicode/homoglyphs and blocks prompt-injection attempts; `redaction.py` strips API keys and sensitive tokens from logs and error responses.
- **HTTP & CORS security:** `SecurityHeadersMiddleware` sets CSP, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, and `Permissions-Policy`. Production CORS rejects wildcard `*` and non-HTTPS origins.
- **Trusted proxy validation:** `TRUSTED_PROXY_IPS` restricts `X-Forwarded-For` parsing; SSRF-safe server-side geocoding proxy (`locations.py`) forwards only allowlisted fields.
- **Static & dependency audits:** `bandit -r app/ -ll` (0 medium/high findings), `pip-audit`, and `npm audit --audit-level=high` (0 vulnerabilities).

## 2. Code Quality & Tooling
- **Backend:** Ruff (`E, F, I, W, UP, B, SIM, PIE, RUF, PERF, PLE, C90, S`), `ruff format`, and `mypy` with `pydantic.mypy` plugin (`disallow_untyped_defs`, `warn_return_any`).
- **Frontend:** TypeScript strict mode (`tsc --noEmit`), ESLint 9 flat config (`eqeqeq`, `no-unused-vars`, `no-var`, `prefer-const`, `no-console`).
- **Station Comparison:** Differential analysis compares live CPCB station observations and coordinate grid fallbacks cleanly without mixing incompatible scales.

## 3. Accessibility & Testing
- **Backend:** Pytest unit + adversarial suites (`coverage report --fail-under=80`, 91%+ coverage). Live provider tests in `tests/integration/` are marked `@pytest.mark.integration` and `@pytest.mark.live` and skipped by default in CI.
- **Frontend:** Vitest + React Testing Library + `vitest-axe` accessibility audits (0 axe violations across `HomePage`, `HouseholdProfileDialog`, `SustainableAlternativesView`, and `ChatAssistant`) + Playwright E2E spec (`frontend/tests/e2e/breathewise.spec.ts`).
