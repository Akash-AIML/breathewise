# Milestone 3 report — verification, audits, shared rate limiting, publication

Date: 2026-11-25. Status: **engineering work and audits completed locally; live CPCB and deployment
remain blocked and are reported as such.**

## 1. What was attempted and what actually happened

| Milestone item | Actual outcome |
|---|---|
| Run opt-in live CPCB tests, record response shape/total/filter status | **Failed because the provider is unreachable.** `RUN_LIVE_TESTS=1 CPCB_READ_TIMEOUT_SECONDS=4 CPCB_MAX_RETRIES=0 pytest tests/integration -m live -q` → `1 failed, 1 passed`: CPCB raised `CPCBTemporaryError: CPCB provider timed out`; the Open-Meteo live test passed. No response body, total, or filter status was observed. |
| Fix the gate that made live tests impossible | `backend/tests/conftest.py` previously blanked provider keys unconditionally. It now blanks them only when `RUN_LIVE_TESTS != 1`, so opt-in tests can actually see configured keys. |
| Verify pollutant averaging period | **Blocked.** Unfiltered / state / city probes timed out at 8.5 s / 8.4 s / 8.5 s; a prior 12 s probe timed out at 12.6 s; a public CPCB documentation fetch failed with a transport error; data.gov.in metadata returned 403. `CPCB_AVERAGING_PERIOD_VERIFIED` stays `false`. |
| Accessibility audit artifact | `axe-core` + `vitest-axe` added. First run found 3 real critical violations in the profile dialog; fixed with `id`/`htmlFor` associations. Final run: **HomePage 21 rules / 0 violations, dialog 20 rules / 0 violations**, `npm run test:ci` **47 passed**. |
| Lighthouse | Real Chromium 155 available; `lighthouse@12.2.1` installed in temporary tooling (not a project dep). Local dev-server scores: **performance 74, accessibility 100, best practices 96, SEO 100**. Performance limited by 1,430 ms total blocking time in dev mode; console errors came from local dev proxy resets while the backend retried CPCB timeouts. Not production scores. |
| Dependency/security audit | `npm audit`: 8 vulnerabilities (4 moderate, 2 high, 2 critical) in dev/build tooling (`next`, `postcss`, `vite`, `vitest`, `esbuild`, `tinypool`, `@vitest/mocker`, `vite-node`). `pip-audit`: `No known vulnerabilities found`. Raw outputs saved. |
| Saved coverage artifacts | `coverage.xml`, `coverage-html/`, regenerated from final run: **85% app-only, 90% all measured modules**. |
| Performance measurements | 140 serial in-process ASGI requests, no outbound HTTP: **p50 0.668 ms, p95 1.038 ms, max 9.157 ms**. Local app-level only. Note: plan requests returned 404 because providers were deliberately disabled; this is recorded, not hidden. |
| Shared rate limiting | Pluggable store added: in-memory default, opt-in Redis with atomic Lua `INCR`/`PEXPIRE`/`PTTL`, bounded timeouts, fail-open on store errors, no credential logging. 8 new mocked tests; **Redis itself was not run**. |
| Demo video | Real 37.2 s screen recording of the local verification instance created with Chromium/Playwright and converted with ffmpeg: `docs/artifacts/breathewise-demo.mp4`. No synthetic video. |
| LinkedIn process doc | `docs/LINKEDIN_PROCESS.md` written from measured work only. |
| Public GitHub repository | **Published.** `git commit` produced `c59d018`; `gh repo create breathewise --public --source=... --remote=origin --push` created `https://github.com/Akash-AIML/breathewise`. Verified `visibility: PUBLIC`, `isPrivate: false`, and local HEAD equals remote HEAD. No `.env` is tracked. |
| Deployment | **Blocked.** No Render/Vercel credentials or CLIs found. `docs/DEPLOYMENT_STATUS.md` records the exact checks. |

## 2. Files added or changed in this milestone

- `backend/tests/conftest.py` — opt-in-aware key isolation (bug fix).
- `backend/app/core/security.py`, `backend/app/core/config.py`, `backend/requirements.txt`,
  `backend/tests/unit/test_security_rate_limit.py`, `docs/RATE_LIMITING.md` — shared rate-limit store.
- `frontend/package.json`, `frontend/package-lock.json`, `frontend/src/test/setup.ts`,
  `frontend/src/test/accessibility.test.tsx` — automated axe audit.
- `frontend/src/components/profile/household-profile-dialog.tsx` — label associations found by axe.
- `docs/CPCB_INTEGRATION.md` — new live-probe evidence and unchanged unverified status.
- `docs/DEMO_SCRIPT.md`, `docs/LINKEDIN_PROCESS.md`, `docs/DEPLOYMENT_STATUS.md`,
  `docs/MILESTONE_3_REPORT.md`, `docs/artifacts/**` — artifacts and documentation.

## 3. Final verified gates

| Command | Actual result |
|---|---|
| `cd backend && .venv/bin/ruff check .` | `All checks passed!` |
| `cd backend && .venv/bin/ruff format --check .` | `50 files already formatted` |
| `cd backend && .venv/bin/python -m pytest tests/ -q` | **130 passed, 2 skipped, 2 warnings** |
| `cd backend && .venv/bin/python -m coverage report --include='app/*'` | **85%** (1803 stmts, 266 missed) |
| `cd frontend && npm run test:ci` | **47 passed** (13 files) |
| `cd frontend && npm run type-check` | clean |
| `cd frontend && npm run build` | clean; First Load JS 240 kB |

## 4. Six-parameter assessment (updated)

| Parameter | Assessment |
|---|---|
| Code quality | Good — single config/adapter, typed schemas, pluggable rate-limit store, lint/format clean. |
| Security | Improved — no-store responses, redaction, hardened prompt screening, shared-store option; 8 npm tooling vulnerabilities remain and are documented. |
| Efficiency | Good — bounded async fetches, cache/coalescing, TTL-based shared counters; local p95 ~1 ms. |
| Testing | Strong locally — 130 backend + 47 frontend tests, axe and Lighthouse run, live test honestly failing due to provider outage. |
| Accessibility | Evidence-backed locally — axe 0 violations, Lighthouse accessibility 100; contrast not evaluated in jsdom, Lighthouse was dev-mode. |
| Problem alignment | Partial — precision/provenance/honesty implemented; live CPCB, averaging period, deployment and production metrics still unverified. |

## 5. Devil's advocate findings

- A passing live Open-Meteo test does **not** validate CPCB; the CPCB live test failed.
- Lighthouse accessibility 100 was measured in dev mode on one page state; it is not a full WCAG audit of every tab/modal state.
- Lighthouse performance 74 is a dev-server number; it must not be presented as production performance.
- The Redis store has no live server test; fail-open means outages silently disable throttling.
- `npm audit` found critical vulnerabilities in dev tooling. They are real and unresolved.
- The demo video is a local instance, not a deployed product.
- 85% coverage does not prove provider fidelity; no live CPCB response has ever been observed here.

## 6. Publication evidence

Commands actually run:

```bash
git add -A                         # after restoring the generated tsconfig.tsbuildinfo
git check-ignore -v .env           # .gitignore:5:.env
git commit -m "Integrate CPCB data, audits, shared rate limiting, and verification artifacts"
# [main c59d018] ... 85 files changed, 17080 insertions(+), 773 deletions(-)
gh repo create breathewise --public --source=/home/akash/Projects/AirQuality --remote=origin --push
# https://github.com/Akash-AIML/breathewise
gh repo view Akash-AIML/breathewise --json name,visibility,isPrivate,url,defaultBranchRef
# visibility PUBLIC, isPrivate false, main
git rev-parse HEAD                 # c59d01812632ef914312041b11a5ca6997b788ba
git ls-remote origin HEAD          # c59d01812632ef914312041b11a5ca6997b788ba
git ls-tree -r --name-only HEAD | grep -E '(^|/)\.env$'   # no matches
```

Publishing the source does **not** mean the application is deployed. No Render or Vercel service was created.

## 7. Remaining work

1. Re-run live CPCB tests on a network where data.gov.in responds; record real total/filters and update `CPCB_INTEGRATION.md`.
2. Verify the averaging-period contract before enabling official AQI.
3. Remediate the 8 npm audit findings with a controlled dependency upgrade and re-run gates.
4. Run a real Redis instance to validate the shared store end-to-end.
5. Deploy with real platform credentials (see `DEPLOYMENT_STATUS.md`) and re-run Lighthouse against the production build.
