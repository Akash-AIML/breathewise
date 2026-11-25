# Code-quality refactor report — file-size reduction

Date: 2026-11-25  
Scope: `backend/app`, `backend/tests`, `frontend/src`  
Goal: split every source or test file exceeding 300 lines into focused modules without changing behaviour, public imports, exact-coordinate handling, or UI text.

## 1. What changed

### Before → after (line counts)

| Original file | Before | Resulting files (current line counts) |
|---|---:|---|
| `backend/app/adapters/cpcb.py` | 806 | `cpcb.py` 169, `cpcb_parsing.py` 270, `cpcb_queries.py` 143, `cpcb_transport.py` 282 |
| `backend/app/core/policy_engine.py` | 574 | `policy_engine.py` 85, `policy_guidance.py` 178, `policy_plan.py` 135, `policy_plan_sections.py` 246 |
| `backend/app/services/llm_assistant_service.py` | 620 | `llm_assistant_service.py` 296, `llm_providers.py` 145, `deterministic_assistant.py` 171, `llm_safety.py` 109 |
| `backend/tests/unit/test_ai_assistant.py` | 723 | `test_ai_assistant.py` 139, `test_ai_assistant_failover.py` 265, `test_ai_assistant_fallback.py` 236, `conftest.py` 111 (shared fixtures) |
| `backend/tests/unit/test_cpcb_integration.py` | 517 | `test_cpcb_integration.py` 105, `test_cpcb_adapter.py` 189, `test_cpcb_normalization.py` 197, `cpcb_helpers.py` 69 (shared helpers) |
| `frontend/src/app/page.tsx` | 947 | `page.tsx` 258, plus `dashboard/hero-banner.tsx` 165, `navigation-tabs.tsx` 102, `overview-panel.tsx` 120, `observation-summary.tsx` 162, `pollutant-breakdown.tsx` 47, `insights-panels.tsx` 121, `map-panel.tsx` 61, `secondary-panels.tsx` 53, `use-location-state.ts` 162 |
| `frontend/src/components/assistant/chat-assistant.tsx` | 362 | `chat-assistant.tsx` 210, `message-bubble.tsx` 110, `quick-prompts.tsx` 39, `assistant-api.ts` 21 |

`find backend/app backend/tests frontend/src -type f \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' \) -print0 | xargs -0 wc -l | sort -rn | awk '$1 > 300 && $2 != "total"'` now returns **no files**. Generated `docs/artifacts/coverage-html/`, `docs/artifacts/coverage.xml`, and `docs/artifacts/README.md` were regenerated so the published evidence matches the new measurement. Two generated-only diffs (`axe-results.json`, `tsconfig.tsbuildinfo`) were restored to `HEAD` to keep this change focused.

### Functionality preserved

- Public imports still work: `CPCBAdapter`/errors/`redact_secrets`, all `policy_engine` functions and `EMISSION_FACTORS`, `LLMAssistantService`/`normalize_for_screening`, default `HomePage`, and named `ChatAssistant`.
- CPCB request budget, circuit breaker, stale fallback, redacted logging, filter verification, and normalization were moved verbatim into mixin modules.
- The LLM chain, per-model timeouts, 20 s total budget, thought-part skipping, exact JSON-schema prompt, and all grounding guards are unchanged.
- Exact device coordinates remain authoritative for every feature; reverse-geocode labels, UI strings, roles, and aria attributes were moved without rewording.
- Shared fixtures/helpers were moved to `tests/unit/conftest.py` and `tests/unit/cpcb_helpers.py`; every original test remains discoverable.

## 2. Checks executed and actual results

| Check | Result |
|---|---|
| `cd backend && .venv/bin/ruff check .` | All checks passed |
| `.venv/bin/ruff format --check .` | 65 files already formatted |
| `.venv/bin/python -m pytest tests/ -q` | **143 passed, 2 skipped**, 2 pre-existing Starlette 422-deprecation warnings |
| `.venv/bin/coverage run -m pytest tests/ -q` + `coverage report --include='app/*'` | **87%** app coverage (2025 statements, 271 missed); all measured modules 91% (3334/303) |
| `cd frontend && npm run test:ci` | **14 test files, 54 tests passed** |
| `npm run type-check` | Clean, no TypeScript errors |
| `npm run build` | Clean; `/` prerendered static, First Load JS **241 kB** |
| Policy equivalence probe (agent) | 1,978 AQI/profile/commute combinations compared with pre-refactor `HEAD`; **0 mismatches** |
| Live smoke after restarting both servers | `/health` 200, `/` 200 |
| `GET /api/v1/air-quality?lat=11.4953&lon=77.2793` through Next proxy | **200 in 5.32 s** |
| Tier-2 browser check at `11.4953, 77.2793` | `Using exact device coordinates (11.4953, 77.2793). Located in Sathyamangalam, Tamil Nadu (OpenStreetMap).`; coordinate line preserved; Bengaluru mislabel **false**; reverse calls **1** |
| `POST /api/v1/assistant/chat` through Next proxy | **200 in 6.68 s**, `llm_grounded: true`, AQI 53 preserved |
| Backend log for that chat | `LLM explanation generated with gemini-3.1-flash-lite` — no key or credentialed URL logged |

## 3. Six-parameter assessment

| Parameter | Assessment | Evidence / caveat |
|---|---|---|
| CODE QUALITY | **Pass** | No file in the scoped source/test tree exceeds 300 lines; modules are organised by concern; public API re-exported. Caveat: facades and mixins add one level of indirection. |
| SECURITY | **Pass, no regression** | No secret handling changed; redaction tests pass; live log names only the model. No key or credentialed URL appeared in output. |
| EFFICIENCY | **Pass, no regression** | No new network call was introduced; tier-2 smoke made one reverse-geocode call; assistant answered in 6.68 s. First Load JS rose 240 → 241 kB, so this was **not** a bundle-size optimisation. |
| TESTING | **Pass** | Backend 143/2, frontend 54/54, app coverage 87%. No new tests were added because this was a move-only change; existing tests cover the preserved behaviour. |
| ACCESSIBILITY | **Pass, no new regression** | Roles/aria attributes and UI text were moved verbatim and role-based tests pass. No fresh axe/Lighthouse audit was run in this phase; the existing `axe-results.json` was left untouched. |
| PROBLEM ALIGNMENT | **Pass** | Exact coordinates still reach air-quality, plan, trend, reverse-geocode, and assistant features; tier-2 label remains grounded in OpenStreetMap rather than a guessed city. |

## 4. Devil's advocate findings

1. **Line count is a weak proxy for quality.** Splitting reduced file size but did not reduce the frontend bundle (241 kB vs 240 kB). Route-level/lazy loading would be needed for a real load-time gain.
2. **Coverage rose from 86% to 87% without new tests.** The increase reflects the changed statement denominator after adding delegating wrappers, not additional behavioural assurance.
3. **Facades can hide coupling.** `cpcb.py` and `policy_engine.py` now re-export implementations; future edits must go to the owning module or the re-export can drift. Tests patch some private methods, so those patch points were deliberately preserved.
4. **Live LLM availability is variable.** One successful 6.68 s chat with `gemini-3.1-flash-lite` is evidence the refactor works, not an availability SLA; earlier phases observed timeouts, 503s, and deterministic fallback.
5. **Unresolved external limitations are unchanged.** Live CPCB remained unreachable in earlier probes, Chennai/Tamil Nadu filters and the CPCB averaging period are still unverified, deployment remains blocked by missing platform credentials, and npm reports unresolved dev-tooling advisories.
6. **The policy equivalence probe was run by the refactor agent, not the full evaluator independently.** It is supporting evidence only; the authoritative evidence is the full test suite and live smoke checks above.

## 5. Remaining issues / next milestone

- Add route-level lazy loading if the 241 kB First Load JS becomes a performance target.
- Re-run axe and Lighthouse against the refactored markup in a fresh browser session before claiming a new accessibility/performance score.
- Revisit live CPCB verification, filter confirmation, and deployment once credentials/network access are available.
- Next milestone: keep this module layout stable and add focused tests for any future logic added to the new modules, rather than growing the facades again.
