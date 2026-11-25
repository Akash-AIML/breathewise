"""Local, in-process ASGI latency measurement for the BreatheWise backend.

This is NOT a production benchmark: requests go through httpx ASGITransport
(no socket, no network, no browser). Provider credentials are cleared and all
provider adapter fetches are patched to return no data, so the numbers measure
the local FastAPI application stack only.

Run from backend/:  .venv/bin/python ../docs/artifacts/measure-performance.py
"""

import asyncio
import json
import math
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Clear provider credentials before importing the app (pydantic-settings gives
# environment variables precedence over the repository .env file).
for key in (
    "DATA_GOV_IN_API_KEY",
    "OPENAQ_API_KEY",
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
):
    os.environ[key] = ""

import httpx  # noqa: E402
from httpx import ASGITransport  # noqa: E402

from app.adapters.cpcb import CPCBAdapter  # noqa: E402
from app.adapters.openaq import OpenAQAdapter  # noqa: E402
from app.adapters.openmeteo import OpenMeteoAdapter  # noqa: E402
from app.main import app  # noqa: E402

OUTPUT = Path(__file__).resolve().parent / "performance.json"

REQUEST_MIX = [
    ("health", "GET", "/health", None, 50),
    ("stations", "GET", "/api/v1/stations", None, 50),
    ("air_quality", "GET", "/api/v1/air-quality?lat=28.6289&lon=77.2407", None, 20),
    (
        "plan",
        "POST",
        "/api/v1/recommendations/plan",
        {"lat": 28.6289, "lon": 77.2407, "profile": {"home_area_sqft": 650}},
        20,
    ),
]


def summarize(values_ms):
    ordered = sorted(values_ms)
    count = len(ordered)
    if count == 0:
        return {"count": 0}
    return {
        "count": count,
        "p50_ms": round(ordered[math.ceil(0.50 * count) - 1], 3),
        "p95_ms": round(ordered[math.ceil(0.95 * count) - 1], 3),
        "max_ms": round(ordered[-1], 3),
        "total_ms": round(sum(ordered), 3),
    }


async def main():
    # No outbound HTTP from any provider adapter: every upstream call returns
    # "no data", exercising the app's honest-degraded path deterministically.
    with (
        patch.object(CPCBAdapter, "fetch_by_coordinates", new=AsyncMock(return_value=None)),
        patch.object(CPCBAdapter, "get_station_observations", new=AsyncMock(return_value=[])),
        patch.object(CPCBAdapter, "fetch_nearby", new=AsyncMock(return_value=[])),
        patch.object(OpenAQAdapter, "fetch_by_coordinates", new=AsyncMock(return_value=None)),
        patch.object(OpenMeteoAdapter, "fetch_by_coordinates", new=AsyncMock(return_value=None)),
    ):
        samples = {name: [] for name, _, _, _, _ in REQUEST_MIX}
        statuses = Counter()
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://asgi-local"
        ) as client:
            for name, method, url, payload, count in REQUEST_MIX:
                for _ in range(count):
                    started = time.perf_counter()
                    response = await client.request(method, url, json=payload)
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    samples[name].append(elapsed_ms)
                    statuses[f"{name}:{response.status_code}"] += 1

    all_samples = [value for values in samples.values() for value in values]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Local in-process ASGI latency only - not production, network, browser, or load-test performance",
        "method": "httpx.AsyncClient(transport=ASGITransport(app=app)); requests issued serially",
        "percentile_method": "nearest-rank on sorted per-request elapsed milliseconds",
        "python": sys.version.split()[0],
        "httpx": httpx.__version__,
        "provider_keys": "cleared in os.environ before importing app.main",
        "network_access": "all provider adapter fetches patched to return no data; no outbound HTTP",
        "request_mix": {name: count for name, _, _, _, count in REQUEST_MIX},
        "status_counts": dict(sorted(statuses.items())),
        "overall": summarize(all_samples),
        "by_endpoint": {name: summarize(values) for name, values in samples.items()},
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
