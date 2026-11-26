# Deployment status

Status: **not deployed from this environment.** This file records the checks performed so that
the absence of a deployment is explicit rather than implied.

## What exists

- `vercel.json` at the repository root — Vercel Services config with an internal FastAPI
  `backend` service, a public Next.js `frontend` service, and a `frontend` → `backend` service
  binding injected as `BACKEND_URL`.
- `backend/render.yaml` — alternative Render web service blueprint (`breathewise-backend`,
  `ENVIRONMENT=production`, `healthCheckPath: /health`, provider keys injected with `sync: false`).
- These are configuration templates only. Neither has been applied to a live platform here.

## Checks actually run

| Check | Actual result |
|---|---|
| Environment variable names containing `RENDER_API_KEY`, `VERCEL_TOKEN`, `VERCEL_API_KEY` | none present |
| Environment variable names containing provider keys | `DATA_GOV_IN_API_KEY` present; others absent or placeholders |
| `command -v vercel` / `command -v render` | no output (CLIs not installed) |
| `~/.config` entries for vercel/render/netlify/fly | none |
| `gh auth status` | authenticated as `Akash-AIML`, scopes include `repo` and `workflow` |

Local uvicorn/Next.js processes used earlier were verification servers on the developer machine.
They were stopped and are **not** a deployment.

## What is blocked

Creating a Render or Vercel deployment requires platform credentials or an interactive browser
login that is not available in this environment. No deployment URL can be reported honestly until
that authentication exists and a deployment succeeds.

## Publishing status

GitHub CLI authentication was available, and the public repository was created at
https://github.com/Akash-AIML/breathewise (commit `c59d018`). Source publication does **not** imply a
running application: no Render or Vercel service was created and no deployment URL exists.
