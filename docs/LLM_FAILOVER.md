# Free-tier Gemini model failover

The assistant tries a configured chain of models in order. A rate limit (429),
temporary unavailability (503/5xx), timeout, malformed JSON, or ungrounded answer
on one model automatically moves to the next. If every model fails, the existing
deterministic policy engine answers instead — the assistant never invents AQI,
risk, or actions.

## Requested chain

`GEMINI_MODELS` (comma-separated, order preserved):

1. `gemini-3.1-flash-lite`
2. `gemini-3.5-flash-lite`
3. `gemma-4-31b-it`
4. `gemma-4-26b-a4b-it`

`GROQ_API_KEY`, when present, remains an optional **last resort** after the whole
Gemini chain. It is no longer tried first, because the configured Groq key
returned HTTP 401 during local verification while the free-tier Gemini key worked.

## Live verification (2026-11-25)

`GET /v1beta/models` with the configured key returned HTTP 200 and listed all four
requested model IDs. Per-model `generateContent` probes used a trivial JSON
request with `responseMimeType: application/json`; the key was sent only in the
`x-goog-api-key` header and was never printed or logged.

| Model | `supportedGenerationMethods` | Probe result |
|---|---|---|
| `gemini-3.1-flash-lite` | `generateContent`, `batchGenerateContent`, … | **200** — valid JSON |
| `gemini-3.5-flash-lite` | `generateContent`, `batchGenerateContent`, … | **200** — valid JSON |
| `gemma-4-31b-it` | `generateContent`, `countTokens` | **200**, but first part was `thought: true` prose; with 128 output tokens it ended `MAX_TOKENS`. A 2048-token probe timed out at 30 s. |
| `gemma-4-26b-a4b-it` | `generateContent`, `countTokens` | First probe **503** “high demand”; a later 2048-token probe returned **200** with a thought part followed by a valid JSON part. |

This is direct evidence that failover is needed: one of the four models was
unavailable at probe time, and the Gemma models require special output parsing.

## Implementation

- `backend/app/core/config.py`
  - `GEMINI_MODELS` — ordered chain
  - `LLM_REQUEST_BUDGET_SECONDS = 20.0` — whole-chain wall-clock ceiling, below
    the frontend proxy timeout
  - `GEMINI_MODEL_TIMEOUT_SECONDS = 10.0`, `GEMMA_MODEL_TIMEOUT_SECONDS = 12.0`
- `backend/app/services/llm_assistant_service.py`
  - `_gemini_model_chain()` de-duplicates while preserving priority order
  - `_call_server_llm()` wraps the chain in `asyncio.timeout`, tries each model,
    and logs only the model name and exception **type** (never the key or URL)
  - a 401/403 response, or a 400 whose body says the API key is invalid, stops
    the chain immediately; retrying other models with the same key cannot help
  - `_call_gemini()` uses `responseMimeType: application/json`, a larger output
    budget for Gemma, and ignores `thought: true` parts, reading the last
    non-thought text part
  - `_parse_json_object()` tolerates code fences and surrounding prose; all
    existing grounding checks (AQI, approved actions, control tokens) still run
    on every model's output
  - the system prompt explicitly requires the exact keys `answer`,
    `scientific_rationale`, and `approved_actions`. Without that specification,
    live models returned reasonable prose under keys such as `station`/`aqi`,
    which correctly failed validation and wasted the whole chain.

## Security and cost controls

- The key is sent only in the `x-goog-api-key` request header, never in a URL
  or log line. A regression test asserts a secret key is absent from warnings.
- Every attempt has a bounded timeout and the whole chain has a 20 s budget, so
  a slow provider cannot stall the chat endpoint.
- No retry loops per model: one attempt per model per user request.
- Provider failures degrade to the deterministic engine; they never become a
  500 response or a fabricated answer.

## Tests

`backend/tests/unit/test_ai_assistant.py::TestGeminiModelFailover` covers the
default chain, 429 → next-model failover, thought-part parsing, all-models-down
fallback, invalid-key short circuit, secret redaction, and the explicit JSON
schema in the system prompt. All HTTP is mocked; the default CI suite never
calls a live provider. Backend gates after this change: **143 passed, 2 skipped**,
app coverage **86%**, `ruff check .` and `ruff format --check .` clean.

Live end-to-end check through the Next.js proxy after the schema fix:

- `POST /api/v1/assistant/chat` at `11.4953, 77.2793` → **200 in 18.03 s**,
  `llm_grounded: true`, AQI 53 preserved
- backend log: `gemini-3.1-flash-lite failed (ReadTimeout)` →
  `LLM explanation generated with gemini-3.5-flash-lite`

That is observed failover, not a simulated success. Provider availability varies
between requests — an earlier identical call fell through to the deterministic
engine in 24.9 s after both Gemini models were throttled/unavailable.

Live key behaviour depends on free-tier quota and provider load. The chain makes
the app resilient to those conditions; it cannot guarantee a specific model is
available at any given moment.
