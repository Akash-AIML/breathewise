from app.core.policy_guidance import (
    EMISSION_FACTORS as EMISSION_FACTORS,
)
from app.core.policy_guidance import (
    generate_indoor_guidance as generate_indoor_guidance,
)
from app.core.policy_guidance import (
    generate_sustainable_alternatives as generate_sustainable_alternatives,
)
from app.core.policy_plan import generate_personalized_plan as generate_personalized_plan
from app.schemas.observation import (
    DataQualityStatus,
    NormalizedObservation,
)
from app.schemas.recommendation import (
    EnvironmentalAssessment,
    RiskClassification,
)


def assess_environmental_risk(observation: NormalizedObservation) -> EnvironmentalAssessment:
    """
    STAGE 1: Deterministic Environmental Risk Classification
    Derives risk level, data completeness, and confidence strictly from sensor telemetry.
    """
    aqi = observation.calculated_aqi
    is_stale = observation.data_quality_status == DataQualityStatus.STALE

    if aqi is None:
        return EnvironmentalAssessment(
            risk_level=RiskClassification.MODERATE,
            aqi=None,
            category=None,
            dominant_pollutant=None,
            data_quality=observation.data_quality_status,
            confidence=0.3,
            is_stale=is_stale,
            assessment_summary=(
                "Insufficient sensor data to establish official CPCB AQI. Exercise baseline caution."
            ),
        )

    # Map CPCB AQI to risk classification
    if aqi <= 50:
        risk = RiskClassification.LOW
        summary = "Air quality is satisfactory and poses little or no health risk to the public."
    elif aqi <= 100:
        risk = RiskClassification.LOW
        summary = "Air quality is acceptable. Minor breathing discomfort may occur for highly sensitive individuals."
    elif aqi <= 200:
        risk = RiskClassification.MODERATE
        summary = "Moderate air pollution. Breathing discomfort may impact sensitive groups including children and the elderly."
    elif aqi <= 300:
        risk = RiskClassification.HIGH
        summary = "Poor air quality. Prolonged exposure causes breathing discomfort to most people."
    elif aqi <= 400:
        risk = RiskClassification.VERY_HIGH
        summary = "Very poor air quality. Triggers respiratory illness on prolonged exposure. Significant risk to vulnerable members."
    else:
        risk = RiskClassification.SEVERE
        summary = "Severe air emergency. Affects healthy people and seriously impacts those with existing respiratory or cardiovascular disease."

    confidence = 0.95 if observation.data_sufficiency_met else 0.65
    if is_stale:
        confidence = max(0.2, confidence - 0.3)

    return EnvironmentalAssessment(
        risk_level=risk,
        aqi=aqi,
        category=observation.aqi_category,
        dominant_pollutant=observation.dominant_pollutant,
        data_quality=observation.data_quality_status,
        confidence=round(confidence, 2),
        is_stale=is_stale,
        assessment_summary=summary,
    )


def calculate_hepa_cadr_m3_hr(area_sqft: int) -> int:
    """
    Computes required Clean Air Delivery Rate (CADR in m³/hr) for 5 Air Changes per Hour (ACH).
    Formula: CADR = Area (sqft) * 0.0929 m²/sqft * 2.5m ceiling * 5 ACH ≈ Area * 1.16 m³/hr
    """
    cadr = area_sqft * 0.0929 * 2.5 * 5.0
    return round(cadr)
