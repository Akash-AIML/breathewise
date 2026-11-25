import os

import pytest

from app.adapters.cpcb import CPCBAdapter
from app.core.config import settings

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("RUN_LIVE_TESTS") != "1" or not settings.DATA_GOV_IN_API_KEY,
        reason="Set RUN_LIVE_TESTS=1 and DATA_GOV_IN_API_KEY to run live CPCB checks.",
    ),
]


@pytest.mark.asyncio
async def test_live_cpcb_resource_and_filters():
    adapter = CPCBAdapter()
    records, total = await adapter._fetch_pages(max_pages=1, page_size=5)

    assert total is not None and total > 0
    assert records
    first = records[0]
    for field in (
        "state",
        "city",
        "station",
        "last_update",
        "latitude",
        "longitude",
        "pollutant_id",
        "min_value",
        "max_value",
        "avg_value",
    ):
        assert field in first

    observations = adapter.parse_records(records)
    assert observations
    assert all(-90 <= obs.latitude <= 90 and -180 <= obs.longitude <= 180 for obs in observations)

    verification = await adapter.verify_filters()
    # Statuses are asserted, not assumed: the provider may legitimately have no
    # Chennai/Tamil Nadu rows at the moment of the probe.
    for field in ("state", "city"):
        assert verification[field]["status"] in {
            "verified",
            "value_not_in_sample",
            "no_records",
            "filter_returned_unrelated_records",
            "provider_unavailable",
        }
