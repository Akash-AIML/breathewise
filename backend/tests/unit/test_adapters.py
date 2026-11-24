import pytest

from app.adapters.cpcb import CPCBAdapter
from app.adapters.openaq import OpenAQAdapter
from app.adapters.openmeteo import OpenMeteoAdapter
from app.schemas.observation import PollutantType


@pytest.mark.asyncio
async def test_cpcb_adapter_parsing():
    adapter = CPCBAdapter(api_key="mock_test_key")
    mock_records = [
        {
            "station": "Test Station Delhi",
            "city": "Delhi",
            "state": "Delhi",
            "pollutant_id": "PM2.5",
            "pollutant_avg": "75.0",
            "pollutant_unit": "µg/m³",
            "last_update": "24-11-2026 14:00:00",
        },
        {
            "station": "Test Station Delhi",
            "city": "Delhi",
            "state": "Delhi",
            "pollutant_id": "PM10",
            "pollutant_avg": "140.0",
            "pollutant_unit": "µg/m³",
            "last_update": "24-11-2026 14:00:00",
        },
        {
            "station": "Test Station Delhi",
            "city": "Delhi",
            "state": "Delhi",
            "pollutant_id": "NO2",
            "pollutant_avg": "55.0",
            "pollutant_unit": "µg/m³",
            "last_update": "24-11-2026 14:00:00",
        },
    ]

    obs = adapter._parse_records_to_observation(mock_records, 28.61, 77.21)
    assert obs is not None
    assert obs.provider == "cpcb_ogd"
    assert obs.station.city == "Delhi"
    assert obs.data_sufficiency_met is True
    assert obs.calculated_aqi is not None
    assert PollutantType.PM2_5.value in obs.readings


@pytest.mark.asyncio
async def test_openaq_adapter_co_unit_conversion():
    adapter = OpenAQAdapter(api_key="mock_key")
    mock_loc = {
        "id": 9999,
        "name": "Connaught Place",
        "locality": "Delhi",
        "coordinates": {"latitude": 28.63, "longitude": 77.22},
    }
    # CO reported in µg/m³ should be converted to mg/m³
    mock_meas = [
        {"parameter": "pm25", "value": 60.0, "unit": "µg/m³", "datetime": "2026-11-24T12:00:00Z"},
        {"parameter": "pm10", "value": 110.0, "unit": "µg/m³", "datetime": "2026-11-24T12:00:00Z"},
        {"parameter": "co", "value": 2500.0, "unit": "µg/m³", "datetime": "2026-11-24T12:00:00Z"},
    ]

    obs = adapter._parse_openaq_data(mock_loc, mock_meas, 28.63, 77.22)
    assert obs is not None
    assert obs.provider == "openaq"
    # CO 2500 µg/m³ -> 2.5 mg/m³
    co_reading = obs.readings[PollutantType.CO.value]
    assert co_reading.value == 2.5
    assert co_reading.unit == "mg/m³"


@pytest.mark.asyncio
async def test_openmeteo_adapter_parsing():
    adapter = OpenMeteoAdapter()
    mock_data = {
        "elevation": 215.0,
        "current": {
            "time": "2026-11-24T15:00",
            "pm2_5": 55.4,
            "pm10": 98.2,
            "nitrogen_dioxide": 42.1,
            "sulphur_dioxide": 18.0,
            "carbon_monoxide": 1200.0,  # µg/m³ -> 1.2 mg/m³
            "ozone": 65.0,
        },
    }
    obs = adapter._parse_response(mock_data, 28.6139, 77.2090)
    assert obs is not None
    assert obs.provider == "openmeteo_cams"
    assert obs.data_sufficiency_met is True
    assert obs.calculated_aqi is not None
    assert obs.station.elevation_m == 215.0
    assert obs.readings[PollutantType.CO.value].value == 1.2
    assert obs.readings[PollutantType.CO.value].unit == "mg/m³"
