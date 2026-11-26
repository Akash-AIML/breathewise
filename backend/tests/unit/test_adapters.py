from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import AsyncClient, MockTransport, Response

from app.adapters.cpcb import CPCBAdapter, CPCBResponseError
from app.adapters.openaq import OpenAQAdapter
from app.adapters.openmeteo import OpenMeteoAdapter
from app.core.config import settings
from app.schemas.observation import PollutantType
from app.services.air_quality_service import INDIAN_CITIES_REGISTRY

_CPCB_TEST_TIMESTAMP = datetime.now(UTC).isoformat()


def _cpcb_record(pollutant_id: str, avg: str, **overrides):
    record = {
        "country": "India",
        "state": "Delhi",
        "city": "Delhi",
        "station": "ITO",
        "last_update": _CPCB_TEST_TIMESTAMP,
        "latitude": 28.6289,
        "longitude": 77.2407,
        "pollutant_id": pollutant_id,
        "min_value": "10.0",
        "max_value": "100.0",
        "avg_value": avg,
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_cpcb_adapter_parsing_uses_actual_schema_without_inventing_units():
    adapter = CPCBAdapter(api_key="mock_test_key", station_registry=INDIAN_CITIES_REGISTRY)
    mock_records = [
        _cpcb_record("PM2.5", "75.0"),
        _cpcb_record("PM10", "140.0"),
        _cpcb_record("NO2", "55.0"),
    ]

    obs = adapter._parse_records_to_observation(mock_records, 28.61, 77.21)
    assert obs is not None
    assert obs.provider == "CPCB/data.gov.in"
    assert obs.station.city == "Delhi"
    assert obs.station.station_name == "ITO"
    assert obs.station.latitude == 28.6289
    assert obs.calculated_aqi is None
    assert obs.data_sufficiency_met is False
    assert "averaging period of avg_value has not been verified" in obs.notes
    assert PollutantType.PM2_5.value in obs.readings
    assert obs.readings[PollutantType.PM2_5.value].unit is None
    assert obs.readings[PollutantType.PM2_5.value].averaging_period_hours is None


@pytest.mark.asyncio
async def test_cpcb_adapter_calculates_aqi_only_when_averaging_is_verified(monkeypatch):
    monkeypatch.setattr(settings, "CPCB_AVERAGING_PERIOD_VERIFIED", True)
    adapter = CPCBAdapter(api_key="mock_test_key")
    records = [
        _cpcb_record("PM2.5", "75.0"),
        _cpcb_record("PM10", "140.0"),
        _cpcb_record("NO2", "55.0"),
    ]

    obs = adapter._parse_records_to_observation(records, 28.61, 77.21)
    assert obs is not None
    assert obs.calculated_aqi is not None
    assert obs.data_sufficiency_met is True
    assert obs.readings[PollutantType.PM2_5.value].averaging_period_hours == 24


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
    assert obs.readings[PollutantType.PM2_5.value].averaging_period_hours == 1
    assert "24-hour averaging unavailable" in obs.notes


def test_cpcb_preserves_unregistered_station_instead_of_relabelling_coordinates():
    adapter = CPCBAdapter(api_key="mock_test_key", station_registry=INDIAN_CITIES_REGISTRY)
    records = [
        _cpcb_record(
            "PM2.5",
            "75.0",
            station="Unknown Rural Station",
            city="Unknown",
            state="Unknown",
            latitude=12.3456,
            longitude=80.1234,
        )
    ]

    obs = adapter._parse_records_to_observation(records, 28.61, 77.21)
    assert obs is not None
    assert obs.station.station_name == "Unknown Rural Station"
    assert obs.station.latitude == 12.3456
    assert obs.station.longitude == 80.1234
    assert obs.station.city == "Unknown"


def test_openmeteo_trend_uses_last_24_completed_hours_with_rolling_averages():
    adapter = OpenMeteoAdapter()
    start = datetime(2026, 11, 23)
    times = [(start + timedelta(hours=i)).isoformat() for i in range(61)]
    hourly = {
        "time": times,
        "pm2_5": [10.0 + i for i in range(61)],
        "pm10": [20.0 + i for i in range(61)],
        "nitrogen_dioxide": [5.0 + i * 0.5 for i in range(61)],
        "sulphur_dioxide": [3.0 + i * 0.2 for i in range(61)],
        "carbon_monoxide": [1000.0 + i * 10 for i in range(61)],
        "ozone": [20.0 + i for i in range(61)],
    }
    mock_data = {
        "timezone": "Asia/Kolkata",
        "elevation": 215.0,
        "current": {
            # Instantaneous values deliberately differ from the rolling average.
            "time": "2026-11-25T10:30",
            "pm2_5": 999.0,
            "pm10": 999.0,
            "nitrogen_dioxide": 999.0,
            "sulphur_dioxide": 999.0,
            "carbon_monoxide": 999999.0,
            "ozone": 999.0,
        },
        "hourly": hourly,
    }

    obs = adapter._parse_response(mock_data, 28.6139, 77.2090)
    assert obs is not None
    assert len(obs.hourly_trend) == 24
    assert obs.hourly_trend[0].time == "2026-11-24T10:00:00+05:30"
    assert obs.hourly_trend[-1].time == "2026-11-25T09:00:00+05:30"
    assert obs.measurement_timestamp.isoformat() == "2026-11-25T09:00:00+05:30"
    # Latest completed hour's rolling 24-hour PM2.5 average: indices 34..57.
    assert obs.readings[PollutantType.PM2_5.value].value == 55.5
    assert obs.readings[PollutantType.PM2_5.value].averaging_period_hours == 24
    assert obs.hourly_trend[0].pm2_5 == 32.5
    assert all(
        "2026-11-25T10" not in point.time and "2026-11-25T11" not in point.time
        for point in obs.hourly_trend
    )


def test_cpcb_unsupported_pollutant_cannot_count_as_pm25(monkeypatch):
    monkeypatch.setattr(settings, "CPCB_AVERAGING_PERIOD_VERIFIED", True)
    adapter = CPCBAdapter(api_key="mock_test_key")
    records = [
        _cpcb_record("PM10", "80.0"),
        _cpcb_record("NO2", "40.0"),
        _cpcb_record("PM2.5 (unverified)", "999.0"),
    ]

    obs = adapter._parse_records_to_observation(records, 28.61, 77.21)
    assert obs is not None
    assert "pm2.5 (unverified)" not in obs.readings
    assert PollutantType.PM2_5.value not in obs.readings
    assert obs.calculated_aqi is None
    assert obs.data_sufficiency_met is False


def test_cpcb_observation_preserves_station_city_and_state():
    adapter = CPCBAdapter(api_key="mock_test_key")
    record = _cpcb_record(
        "PM2.5", "45.0", state="Karnataka", city="Bengaluru", station="Indiranagar"
    )

    observations = adapter.parse_records([record])
    assert len(observations) == 1
    obs = observations[0]
    assert (obs.station, obs.city, obs.state) == ("Indiranagar", "Bengaluru", "Karnataka")

    normalized = adapter.to_normalized(obs, obs.latitude, obs.longitude, 0.0)
    assert normalized.station.station_name == "Indiranagar"
    assert normalized.station.city == "Bengaluru"
    assert normalized.station.state == "Karnataka"
    assert normalized.station.station_id == "cpcb_karnataka_bengaluru_indiranagar"


def test_cpcb_parse_records_skips_malformed_rows_but_rejects_non_list():
    adapter = CPCBAdapter(api_key="mock_test_key")
    observations = adapter.parse_records([_cpcb_record("PM2.5", "45.0"), None, "not-a-record"])
    assert len(observations) == 1
    assert observations[0].station == "ITO"

    with pytest.raises(CPCBResponseError):
        adapter.parse_records("not a list")


@pytest.mark.asyncio
async def test_openaq_resolves_latest_results_through_sensor_metadata(monkeypatch):
    location = {
        "id": 4242,
        "name": "Connaught Place Sensor Hub",
        "locality": "Delhi",
        "coordinates": {"latitude": 28.63, "longitude": 77.22},
        "sensors": [
            {"id": 10, "parameter": {"name": "pm25", "units": "µg/m³"}},
            {"id": 11, "parameter": {"id": "pm10", "units": "µg/m³"}},
            {"id": 12, "parameter": {"name": "co", "units": "ppm"}},
            {"id": 13, "parameter": {"name": "unsupported", "units": "µg/m³"}},
        ],
    }
    latest = [
        {"sensorsId": 10, "value": 50.0, "datetime": {"utc": "2026-11-24T12:00:00Z"}},
        {"sensorsId": 11, "value": 100.0, "datetime": "2026-11-24T12:00:00Z"},
        {"sensorsId": 12, "value": 1.5, "datetime": {"utc": "2026-11-24T12:00:00Z"}},
        {"sensorsId": 13, "value": 999.0, "datetime": {"utc": "2026-11-24T12:00:00Z"}},
        {"sensorsId": 999, "value": 999.0, "datetime": {"utc": "2026-11-24T12:00:00Z"}},
    ]

    def handler(request):
        if request.url.path.endswith("/latest"):
            return Response(200, json={"results": latest})
        return Response(200, json={"results": [location]})

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: AsyncClient(
            transport=MockTransport(handler), timeout=kwargs.get("timeout")
        ),
    )

    adapter = OpenAQAdapter(api_key="mock_key")
    obs = await adapter.fetch_by_coordinates(28.63, 77.22)
    assert obs is not None
    assert obs.station.station_id == "openaq_4242"
    assert obs.readings[PollutantType.PM2_5.value].value == 50.0
    assert obs.readings[PollutantType.PM10.value].unit == "µg/m³"
    assert obs.readings[PollutantType.CO.value].value == 1.72
    assert obs.readings[PollutantType.CO.value].unit == "mg/m³"
    assert "unsupported" not in obs.readings
    assert obs.measurement_timestamp.isoformat() == "2026-11-24T12:00:00+00:00"


def test_openaq_reported_timestamp_supports_object_string_and_malformed_values():
    parser = OpenAQAdapter._reported_timestamp
    expected = "2026-11-24T12:00:00+00:00"
    assert parser({"datetime": {"utc": "2026-11-24T12:00:00Z"}}).isoformat() == expected
    assert parser({"datetime": "2026-11-24T12:00:00Z"}).isoformat() == expected
    assert parser({"datetime": {"local": "2026-11-24T12:00:00Z"}}) is None
    assert parser({"datetime": {"utc": "not-a-date"}}) is None
    assert parser({"datetime": "not-a-date"}) is None
