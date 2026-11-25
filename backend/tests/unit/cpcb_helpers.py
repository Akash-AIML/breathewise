"""Plain helpers shared by the split CPCB unit-test modules."""

from datetime import datetime, timezone

import httpx

from app.adapters.cpcb import CPCBAdapter
from app.schemas.cpcb import CPCBStationObservation
from app.schemas.observation import DataQualityStatus

SECRET = "unit-test-secret-key"
NOW = datetime.now(timezone.utc).isoformat()


def make_record(**overrides):
    record = {
        "country": "India",
        "state": "Tamil Nadu",
        "city": "Chennai",
        "station": "Velachery",
        "last_update": NOW,
        "latitude": 12.9815,
        "longitude": 80.2182,
        "pollutant_id": "PM2.5",
        "min_value": "10.0",
        "max_value": "90.0",
        "avg_value": "45.5",
    }
    record.update(overrides)
    return record


def make_observation(**overrides):
    values = {
        "state": "Tamil Nadu",
        "city": "Chennai",
        "station": "Velachery",
        "station_id": "cpcb_tamil_nadu_chennai_velachery",
        "latitude": 12.9815,
        "longitude": 80.2182,
        "last_update": datetime.now(timezone.utc),
        "retrieval_timestamp": datetime.now(timezone.utc),
        "freshness": DataQualityStatus.VERIFIED,
    }
    values.update(overrides)
    return CPCBStationObservation(**values)


def adapter_with_mock(handler):
    adapter = CPCBAdapter(api_key=SECRET)
    adapter._client = lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return adapter


def _async_return(value):
    async def fake(*args, **kwargs):
        return value

    return fake


__all__ = [
    "NOW",
    "SECRET",
    "_async_return",
    "adapter_with_mock",
    "make_observation",
    "make_record",
]
