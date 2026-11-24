import pytest

from app.adapters.openmeteo import OpenMeteoAdapter
from app.schemas.observation import DataQualityStatus, PollutantType


@pytest.mark.asyncio
async def test_live_openmeteo_fetch_delhi():
    adapter = OpenMeteoAdapter()
    obs = await adapter.fetch_by_coordinates(28.6139, 77.2090)

    # Must return a valid observation
    assert obs is not None
    assert obs.provider == "openmeteo_cams"
    assert obs.station.latitude == 28.6139
    assert obs.station.longitude == 77.2090

    # Must contain verified readings for criteria pollutants
    assert PollutantType.PM2_5.value in obs.readings
    assert PollutantType.PM10.value in obs.readings

    # Validate that values are genuine non-negative floats
    pm25 = obs.readings[PollutantType.PM2_5.value]
    assert pm25.value >= 0.0
    assert pm25.unit == "µg/m³"

    # Must enforce CPCB data sufficiency and compute official AQI
    assert obs.data_sufficiency_met is True
    assert obs.calculated_aqi is not None
    assert obs.aqi_category is not None
    assert obs.dominant_pollutant is not None
    assert obs.data_quality_status == DataQualityStatus.VERIFIED
