"""Shared fixtures for unit tests in ``tests/unit``.

These were previously defined in ``test_ai_assistant.py``; keeping them here makes
them available to every split test module without changing any test bodies.
"""

from datetime import datetime, timezone

import pytest

from app.schemas.observation import (
    AQICategory,
    DataQualityStatus,
    NormalizedObservation,
    NormalizedPollutantReading,
    PollutantType,
    StationMetadata,
)
from app.schemas.profile import HouseholdProfile
from app.services.llm_assistant_service import LLMAssistantService


@pytest.fixture()
def clean_observation() -> NormalizedObservation:
    return NormalizedObservation(
        provider="openmeteo",
        station=StationMetadata(
            station_id="om_delhi",
            station_name="Delhi CPCB",
            city="Delhi",
            state="Delhi",
            latitude=28.6,
            longitude=77.2,
        ),
        readings={
            "PM2_5": NormalizedPollutantReading(
                pollutant=PollutantType.PM2_5, value=35.0, unit="µg/m³"
            ),
            "PM10": NormalizedPollutantReading(
                pollutant=PollutantType.PM10, value=65.0, unit="µg/m³"
            ),
            "NO2": NormalizedPollutantReading(
                pollutant=PollutantType.NO2, value=25.0, unit="µg/m³"
            ),
        },
        calculated_aqi=75,
        aqi_category=AQICategory.SATISFACTORY,
        dominant_pollutant=PollutantType.PM10,
        data_quality_status=DataQualityStatus.VERIFIED,
        measurement_timestamp=datetime.now(timezone.utc),
        retrieval_timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture()
def severe_observation() -> NormalizedObservation:
    return NormalizedObservation(
        provider="openmeteo",
        station=StationMetadata(
            station_id="om_delhi_severe",
            station_name="Delhi IGI Airport",
            city="Delhi",
            state="Delhi",
            latitude=28.5,
            longitude=77.1,
        ),
        readings={
            "PM2_5": NormalizedPollutantReading(
                pollutant=PollutantType.PM2_5, value=250.0, unit="µg/m³"
            ),
            "PM10": NormalizedPollutantReading(
                pollutant=PollutantType.PM10, value=380.0, unit="µg/m³"
            ),
            "NO2": NormalizedPollutantReading(
                pollutant=PollutantType.NO2, value=120.0, unit="µg/m³"
            ),
        },
        calculated_aqi=350,
        aqi_category=AQICategory.VERY_POOR,
        dominant_pollutant=PollutantType.PM2_5,
        data_quality_status=DataQualityStatus.VERIFIED,
        measurement_timestamp=datetime.now(timezone.utc),
        retrieval_timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture()
def unknown_aqi_observation(clean_observation) -> NormalizedObservation:
    return clean_observation.model_copy(
        update={"calculated_aqi": None, "aqi_category": None, "data_sufficiency_met": False}
    )


@pytest.fixture()
def default_profile() -> HouseholdProfile:
    return HouseholdProfile()


@pytest.fixture()
def vulnerable_profile() -> HouseholdProfile:
    return HouseholdProfile(
        has_children=True,
        has_elderly=True,
        has_respiratory_sensitivity=True,
        commute_method="two_wheeler",
    )


@pytest.fixture()
def service() -> LLMAssistantService:
    return LLMAssistantService()
