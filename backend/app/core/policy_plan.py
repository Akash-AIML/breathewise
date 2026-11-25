from typing import List, Optional

from app.core.policy_guidance import (
    generate_indoor_guidance,
    generate_sustainable_alternatives,
)
from app.core.policy_plan_sections import (
    _build_afternoon_recommendations,
    _build_morning_recommendations,
)
from app.schemas.profile import HouseholdProfile
from app.schemas.recommendation import (
    EnvironmentalAssessment,
    PersonalizedPlan,
    RecommendationItem,
)


def _build_evening_recommendations(
    aqi: Optional[int], profile: HouseholdProfile
) -> List[RecommendationItem]:
    evening_items: List[RecommendationItem] = []

    # --- EVENING RECOMMENDATIONS ---
    # Evening rush hour traffic + cooling temperature triggers evening smoke & particulate spike
    if aqi is None:
        evening_items.append(
            RecommendationItem(
                id="rec_eve_aqi_unavailable",
                category="planner",
                title="Limit Optional Outdoor Evening Activities",
                time_of_day="evening",
                action="Choose indoor evening routines until validated AQI is available; re-check official advisories later.",
                priority="medium",
                reason="Evening exposure cannot be risk-assessed without validated telemetry.",
                supporting_evidence="CPCB data-sufficiency rule for official AQI computation.",
                expected_impact="positive_exposure_reduction",
            )
        )
    elif aqi > 150:
        evening_items.append(
            RecommendationItem(
                id="rec_eve_traffic_avoidance",
                category="commute",
                title="Stagger Evening Return Commute",
                time_of_day="evening",
                action="If workplace flexibility allows, depart prior to 5:30 PM or after 8:00 PM to bypass peak arterial idling.",
                priority="medium",
                reason="Vehicular emissions spike dramatically during stop-and-go congestion as evening temperature inversion settles.",
                supporting_evidence="Continuous ambient monitoring stations register secondary diurnal PM2.5 peaks between 6:00 PM and 9:00 PM.",
                expected_impact="balanced",
            )
        )
    else:
        evening_items.append(
            RecommendationItem(
                id="rec_eve_routine_normal",
                category="planner",
                title="Evening Outdoor Leisure Permitted",
                time_of_day="evening",
                action="Evening outdoor leisure, walks, and errands can be conducted without special restrictions.",
                priority="low",
                reason="Air pollution levels remain within acceptable limits for the general population.",
                supporting_evidence="NAAQS 24-hour criteria compliance.",
                expected_impact="balanced",
            )
        )

    # Indoor air preparation for sleep
    if profile.has_air_purifier:
        evening_items.append(
            RecommendationItem(
                id="rec_eve_purifier_boost",
                category="indoor",
                title="Pre-Sleep Bedroom Air Purifier Boost",
                time_of_day="evening",
                action="Turn bedroom air purifier to high speed 45 minutes before bedtime with doors and windows closed, then switch to silent sleep mode.",
                priority="high",
                reason="Rapidly clears daytime dust accumulation and provides clean air during the 7-8 hour sleep regeneration cycle.",
                supporting_evidence="Sleeping in HEPA-filtered air significantly reduces nocturnal airway resistance and morning bronchospasms.",
                expected_impact="positive_exposure_reduction",
            )
        )
    else:
        evening_items.append(
            RecommendationItem(
                id="rec_eve_seal_bedroom",
                category="indoor",
                title="Seal Bedroom Drafts Overnight",
                time_of_day="evening",
                action="Close bedroom windows tightly before dusk and place a rolled towel or draft excluder along the bottom exterior door gap.",
                priority="medium",
                reason="Cool nocturnal air currents pull outdoor pollution into indoor living quarters.",
                supporting_evidence="Infiltration studies show door undercuts account for up to 35% of outdoor dust entry in Indian apartments.",
                expected_impact="positive_exposure_reduction",
            )
        )

    return evening_items


def generate_personalized_plan(
    assessment: EnvironmentalAssessment, profile: HouseholdProfile
) -> PersonalizedPlan:
    """
    STAGE 2: Deterministic Personalization Policy Engine
    Translates environmental risk + household vulnerability into actionable daily routines.
    """

    aqi = assessment.aqi
    is_vulnerable = (
        profile.has_children
        or profile.has_elderly
        or profile.has_respiratory_sensitivity
        or profile.has_cardiovascular_sensitivity
    )

    morning_items: List[RecommendationItem] = _build_morning_recommendations(
        aqi, profile, is_vulnerable
    )
    afternoon_items: List[RecommendationItem] = _build_afternoon_recommendations(aqi, profile)
    evening_items: List[RecommendationItem] = _build_evening_recommendations(aqi, profile)

    indoor_guidance = generate_indoor_guidance(profile, aqi)
    sustainable_alts = generate_sustainable_alternatives(profile, aqi)

    return PersonalizedPlan(
        environmental_assessment=assessment,
        household_profile=profile,
        morning_recommendations=morning_items,
        afternoon_recommendations=afternoon_items,
        evening_recommendations=evening_items,
        indoor_guidance=indoor_guidance,
        sustainable_alternatives=sustainable_alts,
    )
