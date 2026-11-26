from datetime import UTC, datetime

import pytest

from app.core.policy_engine import (
    assess_environmental_risk,
    calculate_hepa_cadr_m3_hr,
    generate_indoor_guidance,
    generate_personalized_plan,
)
from app.schemas.observation import (
    AQICategory,
    DataQualityStatus,
    NormalizedObservation,
    NormalizedPollutantReading,
    PollutantType,
    StationMetadata,
)
from app.schemas.profile import HouseholdProfile
from app.schemas.recommendation import RiskClassification


@pytest.fixture
def mock_observation_severe():
    return NormalizedObservation(
        provider="openmeteo_cams",
        station=StationMetadata(
            station_id="test_delhi",
            station_name="Delhi Station",
            city="Delhi",
            state="Delhi",
            latitude=28.61,
            longitude=77.21,
        ),
        readings={
            "PM2.5": NormalizedPollutantReading(
                pollutant=PollutantType.PM2_5, value=280.0, unit="µg/m³"
            ),
            "PM10": NormalizedPollutantReading(
                pollutant=PollutantType.PM10, value=420.0, unit="µg/m³"
            ),
            "NO2": NormalizedPollutantReading(
                pollutant=PollutantType.NO2, value=150.0, unit="µg/m³"
            ),
        },
        calculated_aqi=410,
        dominant_pollutant=PollutantType.PM2_5,
        aqi_category=AQICategory.SEVERE,
        data_sufficiency_met=True,
        measurement_timestamp=datetime.now(UTC),
        retrieval_timestamp=datetime.now(UTC),
        data_quality_status=DataQualityStatus.VERIFIED,
    )


def test_environmental_risk_assessment_mapping(mock_observation_severe):
    assessment = assess_environmental_risk(mock_observation_severe)
    assert assessment.risk_level == RiskClassification.SEVERE
    assert assessment.aqi == 410
    assert assessment.confidence >= 0.9
    assert assessment.is_stale is False
    assert "Severe" in assessment.assessment_summary


def test_hepa_cadr_calculation():
    # 600 sqft: 600 * 0.0929 * 2.5 * 5 = 696.75 -> 697 m3/hr
    cadr_600 = calculate_hepa_cadr_m3_hr(600)
    assert 690 <= cadr_600 <= 700

    # 1000 sqft: 1000 * 0.0929 * 2.5 * 5 = 1161.25 -> 1161 m3/hr
    cadr_1000 = calculate_hepa_cadr_m3_hr(1000)
    assert 1150 <= cadr_1000 <= 1170


def test_vulnerable_household_prioritization(mock_observation_severe):
    assessment = assess_environmental_risk(mock_observation_severe)

    # Vulnerable family with asthmatic child
    vulnerable_profile = HouseholdProfile(
        has_children=True,
        has_respiratory_sensitivity=True,
        commute_method="bus",
    )
    plan = generate_personalized_plan(assessment, vulnerable_profile)

    # Must contain critical child and morning workout cancellation advice
    morn_titles = [item.title for item in plan.morning_recommendations]
    assert any("Shift Morning Workouts Indoors" in t for t in morn_titles)
    assert any("Child School Commute Protection" in t for t in morn_titles)

    # N95 commute advice must be high/critical priority
    commute_rec = next(item for item in plan.morning_recommendations if "N95" in item.title)
    assert commute_rec.priority in ("critical", "high")


def test_cycling_tradeoff_in_severe_air(mock_observation_severe):
    assessment = assess_environmental_risk(mock_observation_severe)
    profile = HouseholdProfile(commute_method="walking_cycling")
    plan = generate_personalized_plan(assessment, profile)

    cycling_alt = next(
        alt for alt in plan.sustainable_alternatives if "Walking & Cycling" in alt.mode
    )
    # Must explicitly warn about increased respiratory minute ventilation during severe AQI
    assert "CRITICAL EXPOSURE TRADE-OFF" in cycling_alt.condition_dependent_note
    assert "DO NOT cycle" in cycling_alt.condition_dependent_note


def test_houseplant_scientific_disclaimer():
    profile = HouseholdProfile(home_area_sqft=500)
    guidance = generate_indoor_guidance(profile, aqi=200)

    # Must state empirical scientific reality rather than commercial myths
    assert "Scientific Reality" in guidance.houseplant_scientific_disclaimer
    assert "cannot meaningfully purify" in guidance.houseplant_scientific_disclaimer
    assert "NASA" in guidance.houseplant_scientific_disclaimer
