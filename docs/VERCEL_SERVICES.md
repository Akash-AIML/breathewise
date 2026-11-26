# Vercel Services configuration

This document records the repository configuration for deploying the FastAPI backend and Next.js frontend as **one Vercel project with multiple services**. It is configuration work, not evidence of a deployment. No Vercel account, token, or deployment URL was available here.

## Final `vercel.json` (repository root)

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "services": {
    "backend": {
      "root": "backend",
      "framework": "fastapi",
      "entrypoint": "app.main:app",
      "installCommand": "pip install -r requirements.txt",
      "functions": {
        "app/main.py": {
          "maxDuration": 60
        }
      }
    },
    "frontend": {
      "root": "frontend",
      "framework": "nextjs",
      "installCommand": "npm install",
      "buildCommand": "npm run build",
      "outputDirectory": ".next",
      "bindings": [
        {
          "type": "service",
          "service": "backend",
          "format": "url",
          "env": "BACKEND_URL"
        }
      ],
      "functions": {
        "src/app/api/v1/[...path]/route.ts": {
          "maxDuration": 60
        },
        "src/app/health/route.ts": {
          "maxDuration": 60
        }
      }
    }
  },
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": {
        "service": "frontend"
      }
    }
  ]
}
```

`frontend/vercel.json` was removed because it hardcoded a Render hostname and is superseded by the root services config.

## Routing and bindings

| Public path | Handled by | Internal target |
|---|---|---|
| `/` and all non-API pages/static assets | `frontend` | none |
| `/api/v1/*` | `frontend` route handler | `BACKEND_URL` + `/api/v1/*` |
| `/health` | `frontend` route handler | `BACKEND_URL` + `/health` |

The `backend` service has **no top-level public rewrite** and is internal by default. The only caller is the `frontend` service, which declares the binding. Vercel injects the deployment-aware URL into `BACKEND_URL` at runtime. The value is not set in project environment variables, is not a `NEXT_PUBLIC_*` variable, and is not read during builds or middleware.

The frontend route handlers:

- allow only the existing prefixes `air-quality`, `assistant`, `locations`, `recommendations`, and `stations`;
- forward only `Accept`, `Content-Type`, and `X-Requested-With` upstream, so browser cookies, authorization headers, and spoofed forwarded-IP headers are not sent to the backend;
- copy `content-type`, `cache-control`, `retry-after`, and selected security headers back, with `Cache-Control: no-store`;
- use a 24s proxy budget for `/api/v1/assistant/chat` and 15s elsewhere, below the 25s browser assistant timeout; the backend's 20s LLM budget remains the authoritative provider deadline;
- return fixed `503`/`504`/`404` messages without upstream error text.

The backend still owns its `/api/v1` prefix and `/health` route; no route prefix had to be changed.

## Environment variables

Set these in the Vercel project (shared across services):

- `ENVIRONMENT=production` — required so production validation runs.
- `CORS_ORIGINS` — JSON array of HTTPS origins, for example `["https://your-project.vercel.app"]`.
- Provider keys only if used: `DATA_GOV_IN_API_KEY`, `OPENAQ_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`.

Do not set:

- `BACKEND_URL` — injected by the binding.
- `NEXT_PUBLIC_API_BASE_URL` — the browser stays same-origin; a remote value is ignored in production.

Local `next dev` without Vercel still needs `BACKEND_URL=http://127.0.0.1:8000`, set in `frontend/.env.local` or exported in the shell. The root `.env.example` documents this local-only use. `vercel dev` injects the binding automatically.

## Checks actually run locally

| Check | Actual result |
|---|---|
| Root `vercel.json` against the published `https://openapi.vercel.sh/vercel.json` schema | valid with Draft 7 validation |
| `npm run type-check` with `.next` removed | clean; no dependency on generated `RouteContext` types |
| `npm run test:ci` | **76 passed / 18 files**, including service config, binding, timeout, proxy, fresh-geolocation, approximate-fix rejection, and existing axe tests |
| `npm run build` | Next.js 16.4.6 build passed; `/api/v1/[...path]` and `/health` are dynamic route handlers |
| `npm audit --audit-level=moderate` | 0 vulnerabilities |
| Backend `ruff check`, `ruff format --check`, coverage tests, `pip-audit` | clean; **158 passed, 2 skipped**, app coverage **87%**, no known vulnerabilities |
| `BACKEND_URL=http://127.0.0.1:8000 npm run dev -- --port 3001` with local backend on `:8000` | started successfully |
| `GET /health` through Next | `200`, `{"status":"healthy"}` |
| `GET /api/v1/stations?limit=3` through Next | `200`, `count=3` |
| `GET /api/v1/stations/compare?...` through Next | `200`, `basis=coordinate_estimate`, 2 observations |
| `GET /api/v1/stations/comparison-presets` through Next | `200`, fallback grid source, 3 presets |
| `GET /api/v1/admin/debug` through Next | `404`, fixed `Not found.` message, backend not called in unit test |

No Vercel build or deployment was executed, so the service config has not been validated by the platform.

## Details to confirm

Please confirm or correct each of these decisions:

1. Are the service names `backend` and `frontend`?
2. Should only `frontend` be public at `/` (catch-all), with `backend` kept internal and called through the binding?
3. Is the only binding `frontend` → `backend`, injected as `BACKEND_URL`?
4. The 60-second `maxDuration` values and the explicit install/build/output commands were inferred from the repository and Vercel's Python + Next.js guide. Should any of them use different values or be omitted for project defaults?
