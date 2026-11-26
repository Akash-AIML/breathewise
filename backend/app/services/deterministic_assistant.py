"""Deterministic, zero-hallucination explanation engine used as the fallback path."""

from collections.abc import Callable
from typing import Any

from app.schemas.assistant import ExplanationResponse
from app.schemas.observation import NormalizedObservation
from app.schemas.profile import HouseholdProfile
from app.schemas.recommendation import EnvironmentalAssessment, PersonalizedPlan


def render_label(value: Any) -> str:
    """Render enums as human-readable labels in generated explanations."""
    if value is None:
        return "unavailable"
    return str(getattr(value, "value", value))


_FallbackParts = tuple[str, str, list[str]]


def _unavailable_response(
    obs: NormalizedObservation,
    assessment: EnvironmentalAssessment,
    plan: PersonalizedPlan,
) -> ExplanationResponse:
    return ExplanationResponse(
        answer=(
            f"Validated AQI is unavailable at {obs.station.station_name}. I cannot confirm whether "
            "outdoor activity is safe right now. Keep strenuous outdoor plans on hold, use indoor "
            "alternatives, and check validated CPCB telemetry or official advisories before proceeding."
        ),
        referenced_aqi=None,
        dominant_pollutant=obs.dominant_pollutant,
        risk_level=assessment.risk_level,
        approved_actions=[item.action for item in plan.morning_recommendations[:2]],
        scientific_rationale=(
            "CPCB AQI requires at least three valid pollutant sub-indices, one of them particulate."
        ),
        provider_provenance=obs.provider,
        llm_grounded=False,
    )


def _direct_impact_reply(
    obs: NormalizedObservation,
    aqi: int,
    plan: PersonalizedPlan,
    profile: HouseholdProfile,
    label: Callable[[Any], str],
) -> _FallbackParts:
    cadr = plan.indoor_guidance.hepa_sizing_cadr_m3_hr
    answer = (
        f"At {obs.station.station_name} (AQI {aqi}, {label(obs.aqi_category)}), your daily choices create a measurable direct impact:\n"
        f"1. Switching a 16 km/day solo car commute (150 g CO₂/km) to Electric Metro (14 g CO₂/km) cuts ~48 kg CO₂/month (~566 kg/year) "
        f"and reduces roadside PM2.5 inhalation by 50-70% inside filtered carriages.\n"
        f"2. Running a {cadr} m³/hr True HEPA purifier (sized for your {profile.home_area_sqft or 600} sq.ft. home at 5 ACH) "
        f"with sealed window drafts and kitchen chimney exhaust cuts indoor fine particulate exposure substantially compared to ambient air."
    )
    rationale = "ARAI/CEA India transport emission factors and 5-ACH ASHRAE/CPCB mechanical filtration sizing."
    actions = [
        "Use Electric Metro or carpool instead of solo driving or two-wheelers.",
        f"Operate a {cadr} m³/hr HEPA purifier during morning/evening inversion peaks.",
        "Avoid open waste/leaf burning and combine errands into single off-peak trips.",
    ]
    return answer, rationale, actions


def _winter_smog_reply(obs: NormalizedObservation, aqi: int) -> _FallbackParts:
    answer = (
        f"During severe winter smog (current AQI at {obs.station.station_name}: {aqi}), cold ground air forms a thermal inversion lid "
        "between 6:00-9:30 AM and again after 6:30 PM, trapping PM2.5 and combustion soot at breathing height. "
        "Schedule essential errands or brief ventilation for 1:00-4:00 PM when solar warming lifts the boundary layer, "
        "wear a snug N95/FFP2 respirator outdoors, and keep indoor HEPA + kitchen exhaust running."
    )
    rationale = "Diurnal boundary-layer meteorology: winter inversions halve mixing height in early morning and late evening."
    actions = [
        "Avoid outdoor exercise between 6:00-9:30 AM and after 6:30 PM.",
        "Keep windows sealed during inversion hours; ventilate briefly only 1:00-4:00 PM if AQI < 200.",
        "Share community/school alerts to halt open biomass burning and move morning assemblies indoors.",
    ]
    return answer, rationale, actions


def _exercise_reply(
    obs: NormalizedObservation, aqi: int, label: Callable[[Any], str]
) -> _FallbackParts:
    if aqi > 200:
        return (
            (
                f"It is NOT safe to exercise outdoors right now. The current AQI at {obs.station.station_name} "
                f"is {aqi} ({label(obs.aqi_category)}), with {label(obs.dominant_pollutant)} as the dominant pollutant. "
                "Vigorous outdoor exercise increases your minute ventilation rate by up to 500%, pulling fine combustion "
                "soot deep into your alveolar lung tissue. Please shift workouts to an indoor enclosed space."
            ),
            "Cold morning inversion traps PM2.5 in the breathing zone. Exercise escalates inhaled particulate dose.",
            [
                "Cancel outdoor running, jogging, and cycling.",
                "Exercise indoors with windows closed and air purifier active.",
            ],
        )
    return (
        (
            f"Outdoor exercise is acceptable under current conditions (AQI: {aqi}, Category: {label(obs.aqi_category)}). "
            "However, schedule physical activities for mid-afternoon when atmospheric dispersion is greatest."
        ),
        "Particulate levels are within acceptable thresholds for moderate physical activity.",
        ["Keep outdoor workouts to light or moderate intensity."],
    )


def _children_reply(aqi: int, label: Callable[[Any], str], category: Any) -> _FallbackParts:
    if aqi > 150:
        return (
            (
                f"Children should avoid outdoor physical play at this time. With an ambient AQI of {aqi} ({label(category)}), "
                "children are disproportionately vulnerable because their lungs are still developing and they breathe more air "
                "per minute relative to their body weight than adults. Ensure they wear a snug-fitting child-sized N95 mask during school transit."
            ),
            "WHO Child Health guidelines: narrower pediatric airways suffer heightened inflammation from fine particles.",
            [
                "Keep children indoors during morning smog peaks.",
                "Use certified pediatric N95 respirators for school commutes.",
            ],
        )
    return (
        (
            f"Current air quality (AQI: {aqi}, Category: {label(category)}) is within safe limits for children's outdoor play "
            "and school sports."
        ),
        "Criteria pollutants do not exceed national pediatric safety standards.",
        ["Permit standard outdoor school activities."],
    )


def _indoor_reply(plan: PersonalizedPlan, profile: HouseholdProfile) -> _FallbackParts:
    cadr = plan.indoor_guidance.hepa_sizing_cadr_m3_hr
    return (
        (
            f"For your home area (~{profile.home_area_sqft} sq.ft.), a mechanical air purifier delivering a Clean Air Delivery Rate (CADR) "
            f"of at least {cadr} m³/hr is recommended. Regarding houseplants: while aesthetically pleasing, peer-reviewed environmental studies "
            "conclusively prove that houseplants cannot meaningfully filter fine particulate matter (PM2.5) in living rooms. "
            "Only True HEPA filters with dense borosilicate fiber webs capture airborne soot effectively."
        ),
        "Waring et al. (Drexel University, 2019): Plant air cleaning rates are negligible compared to mechanical air exchange.",
        [
            f"Ensure domestic purifier provides at least {cadr} m³/hr CADR.",
            "Vacuum mesh pre-filters every 2 weeks; never wash True HEPA filters with water.",
            "Turn on kitchen chimney exhaust whenever heating cooking oil.",
        ],
    )


def _commute_reply(
    obs: NormalizedObservation, aqi: int, label: Callable[[Any], str]
) -> _FallbackParts:
    if aqi > 100:
        return (
            (
                f"For commuting in current air ({aqi} AQI, {label(obs.dominant_pollutant)}), the electric metro is your safest and cleanest option. "
                "Underground and modern AC metro trains filter out 50-70% of road-level particulate matter while generating 86% less CO2 than a solo car. "
                "If commuting by two-wheeler or non-AC bus, you must wear an authentic N95/FFP2 respirator covering your nose and mouth tightly."
            ),
            "Roadside micro-environments feature localized diesel exhaust peaks up to 3x higher than ambient monitors.",
            [
                "Prefer electric metro transit over surface two-wheeler commute.",
                "Wear a certified N95 respirator (cloth and surgical masks fail against sub-micron PM2.5).",
                "Keep car AC in internal recirculation mode.",
            ],
        )
    return (
        f"Current ambient road air is satisfactory (AQI: {aqi}). Public transit, metro, and active cycling are all acceptable.",
        "Ambient criteria pollutants are within standard limits.",
        ["Standard commute routines without specialized respirators."],
    )


def _general_reply(
    obs: NormalizedObservation,
    aqi: int,
    assessment: EnvironmentalAssessment,
    plan: PersonalizedPlan,
    profile: HouseholdProfile,
    label: Callable[[Any], str],
) -> _FallbackParts:
    is_vulnerable = profile.has_children or profile.has_respiratory_sensitivity
    tail = (
        "Because your household profile includes vulnerable family members (children or respiratory sensitivity), "
        "our policy engine escalated protective precautions."
        if is_vulnerable
        else "Our policy engine generated tailored recommendations for your daily commute and indoor ventilation."
    )
    answer = (
        f"Based on real-time sensor measurements from {obs.station.station_name}, your current AQI is {aqi} "
        f"({label(obs.aqi_category)}), with {label(obs.dominant_pollutant)} as the dominant criteria pollutant. "
        f"We categorized your environmental risk as {assessment.risk_level.value.upper()}. {tail}"
    )
    return (
        answer,
        "CPCB NAQI multi-pollutant sub-index evaluation.",
        [item.action for item in plan.morning_recommendations[:2]],
    )


def generate_deterministic_fallback(
    query: str,
    obs: NormalizedObservation,
    assessment: EnvironmentalAssessment,
    plan: PersonalizedPlan,
    profile: HouseholdProfile,
    label: Callable[[Any], str] = render_label,
) -> ExplanationResponse:
    """Synthesize a structured, zero-hallucination response when LLMs are offline."""
    aqi = obs.calculated_aqi
    if aqi is None:
        return _unavailable_response(obs, assessment, plan)

    q = query.lower()
    if any(w in q for w in ("impact", "saving", "difference", "co2", "choice", "choices")):
        answer, rationale, actions = _direct_impact_reply(obs, aqi, plan, profile, label)
    elif any(w in q for w in ("winter", "smog", "inversion", "stubble", "fog")):
        answer, rationale, actions = _winter_smog_reply(obs, aqi)
    elif any(w in q for w in ("exercise", "workout", "jog", "run", "walk", "sports", "gym")):
        answer, rationale, actions = _exercise_reply(obs, aqi, label)
    elif any(
        w in q
        for w in ("child", "children", "kid", "kids", "baby", "infant", "school", "recess", "play")
    ):
        answer, rationale, actions = _children_reply(aqi, label, obs.aqi_category)
    elif any(
        w in q
        for w in ("plant", "houseplant", "snake plant", "indoor", "purifier", "filter", "cadr")
    ):
        answer, rationale, actions = _indoor_reply(plan, profile)
    elif any(
        w in q for w in ("commute", "travel", "metro", "bus", "car", "bike", "cycle", "mask", "n95")
    ):
        answer, rationale, actions = _commute_reply(obs, aqi, label)
    else:
        answer, rationale, actions = _general_reply(obs, aqi, assessment, plan, profile, label)

    return ExplanationResponse(
        answer=answer,
        referenced_aqi=obs.calculated_aqi,
        dominant_pollutant=obs.dominant_pollutant,
        risk_level=assessment.risk_level,
        approved_actions=actions,
        scientific_rationale=rationale,
        provider_provenance=obs.provider,
        llm_grounded=False,
    )
