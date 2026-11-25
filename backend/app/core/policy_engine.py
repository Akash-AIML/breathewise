from typing import List, Optional

from app.schemas.observation import (
    DataQualityStatus,
    NormalizedObservation,
)
from app.schemas.profile import HouseholdProfile
from app.schemas.recommendation import (
    EnvironmentalAssessment,
    IndoorGuidance,
    PersonalizedPlan,
    RecommendationItem,
    RiskClassification,
    SustainableAlternative,
)

# Documented Indian Emission Factors (ARAI / Central Electricity Authority / BEE Standards)
EMISSION_FACTORS = {
    "car_solo_petrol": 150.0,  # g CO2/passenger-km
    "two_wheeler_petrol": 50.0,  # g CO2/passenger-km
    "car_carpool": 75.0,  # g CO2/passenger-km (2 occupants)
    "city_bus_cng": 30.0,  # g CO2/passenger-km
    "metro_electric": 20.0,  # g CO2/passenger-km (grid-adjusted)
    "walking_cycling": 0.0,  # g CO2/passenger-km
}


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
    return int(round(cadr))


def generate_indoor_guidance(profile: HouseholdProfile, aqi: Optional[int]) -> IndoorGuidance:
    """
    MODULE 5: Evidence-Based Domestic Indoor Guidance.
    Strict scientific grounding: No fake houseplant claims; nuanced ventilation logic.
    """
    area = profile.home_area_sqft or 600
    cadr = calculate_hepa_cadr_m3_hr(area)

    explanation = (
        f"For a domestic carpet area of ~{area} sq.ft. with standard 2.5m ceiling height, "
        f"an air purifier should deliver a minimum Clean Air Delivery Rate (CADR) of {cadr} m³/hr "
        f"to achieve 5 complete air changes per hour (ACH)."
    )

    filter_tips = [
        "Pre-Filter Maintenance: Vacuum or gently wash the nylon mesh pre-filter every 2 to 3 weeks to capture dust and lint.",
        "True HEPA Replacement: Replace True HEPA filters every 6 to 12 months (or when airflow visibly drops).",
        "Never Wash True HEPA Filters: Washing non-washable HEPA filters with water or soap irreversibly collapses the electrostatic microscopic borosilicate fiber web, destroying filtration efficiency.",
        "Carbon Filter Saturation: Replace activated carbon filters when chemical or cooking odors begin lingering indoors.",
    ]

    # Ventilation advice: distinguish outdoor pollution from indoor cooking/combustion sources
    if aqi is None:
        vent_advice = (
            "Official AQI is currently unavailable, so outdoor ventilation safety cannot be established. "
            "Keep windows closed, rely on mechanical filtration, and check validated AQI or official "
            "CPCB advisories before opening the home to outdoor air."
        )
    elif aqi > 250:
        vent_advice = (
            "Keep external windows and balcony doors sealed during early morning and late night inversions. "
            "However, if cooking on gas or if indoor air feels heavy with carbon dioxide, perform brief (10-15 min) "
            "cross-ventilation during mid-afternoon (1 PM - 4 PM) when atmospheric mixing height is highest, "
            "then seal and run HEPA filtration on high mode."
        )
    elif aqi > 100:
        vent_advice = (
            "Open windows for cross-ventilation during warm afternoon hours (12 PM - 3 PM) when ambient particulate "
            "levels dip. Seal windows in early morning hours when cool air traps local emissions near the ground."
        )
    else:
        vent_advice = "Ambient air quality is acceptable. Maintain regular cross-ventilation to prevent domestic CO2 and VOC buildup."

    cooking_precautions = [
        "Chimney / Exhaust Operation: Always engage kitchen exhaust or electric chimney at maximum speed before heating oil or performing 'tadka' (tempering).",
        "Keep Kitchen Partition Doors Closed: Prevent particulate plumes from cooking oil aerosols from spreading to bedrooms.",
        "Avoid Indoor Biomass / Incense: Do not burn dhoop, agarbatti, or scented paraffin candles indoors; their combustion releases concentrated PM2.5, formaldehyde, and polycyclic aromatic hydrocarbons (PAHs).",
    ]

    low_cost = [
        "Wet Mopping over Dry Sweeping: Dry brooms resuspend settled toxic fine dust into the breathing zone. Use damp microfiber mops daily.",
        "Door & Window Draft Seals: Apply low-cost weatherstripping foam tape on outer door frames to block outdoor dust intrusion.",
        "Exhaust Fan Dust Catchers: Place inexpensive activated mesh over exhaust grills to minimize backdraft.",
    ]

    houseplant_disclaimer = (
        "Scientific Reality: Contrary to popular commercial marketing, ordinary indoor houseplants (such as snake plants or areca palms) "
        "cannot meaningfully purify household air in real-world living spaces. The original 1989 NASA Clean Air Study was conducted in tiny, "
        "airtight sealed chambers; multiple independent peer-reviewed studies (e.g. Waring et al., Drexel University) demonstrate that hundreds "
        "of plants would be needed per room to match the clean air exchange rate of a single mechanical HEPA filter."
    )

    return IndoorGuidance(
        hepa_sizing_cadr_m3_hr=cadr,
        hepa_sizing_explanation=explanation,
        filter_maintenance_tips=filter_tips,
        ventilation_advice=vent_advice,
        cooking_smoke_precautions=cooking_precautions,
        practical_low_cost_precautions=low_cost,
        houseplant_scientific_disclaimer=houseplant_disclaimer,
    )


def generate_sustainable_alternatives(
    profile: HouseholdProfile, aqi: Optional[int]
) -> List[SustainableAlternative]:
    """
    MODULE 6: Sustainable Alternatives with Documented Emission Factors.
    Distinguishes emission reduction benefits from personal exposure trade-offs.
    """
    alternatives: List[SustainableAlternative] = []

    # 1. Electric Metro / Urban Rail
    car_factor = EMISSION_FACTORS["car_solo_petrol"]
    metro_factor = EMISSION_FACTORS["metro_electric"]
    metro_reduction = round(((car_factor - metro_factor) / car_factor) * 100, 1)

    alternatives.append(
        SustainableAlternative(
            mode="Electric Rapid Metro (e.g. Delhi Metro, Namma Metro)",
            emission_factor_g_co2_per_km=metro_factor,
            estimated_emission_reduction_pct=metro_reduction,
            personal_exposure_mitigation=(
                "Underground and elevated modern metro carriages utilize recirculated ducted air conditioning "
                "with pre-filters, reducing passenger fine particulate inhalation by 50-70% compared to road-level transit."
            ),
            condition_dependent_note="Recommended regardless of AQI. Wear an N95 respirator during first-mile station access.",
        )
    )

    # 2. Electric / Compressed Natural Gas (CNG) Bus Fleet
    bus_factor = EMISSION_FACTORS["city_bus_cng"]
    bus_reduction = round(((car_factor - bus_factor) / car_factor) * 100, 1)
    alternatives.append(
        SustainableAlternative(
            mode="Public Transit Bus (Electric / CNG)",
            emission_factor_g_co2_per_km=bus_factor,
            estimated_emission_reduction_pct=bus_reduction,
            personal_exposure_mitigation=(
                "Mass transit takes individual private combustion vehicles off congested arterial corridors."
            ),
            condition_dependent_note=(
                "In non-AC city buses with open windows, ambient street-level PM2.5 and exhaust fumes enter directly. "
                "Always wear a snug-fitting N95/FFP2 mask when commuting by open-window bus."
            ),
        )
    )

    # 3. Active Transit (Walking / Cycling) - Evaluated with critical exposure trade-off
    bike_factor = EMISSION_FACTORS["walking_cycling"]
    if aqi is None:
        cycling_note = (
            "Official AQI is unavailable, so outdoor active-transit safety is withheld until validated "
            "telemetry exists. Zero-emission travel remains environmentally preferable, but use metro or "
            "enclosed public transport until exposure conditions are known."
        )
    elif aqi > 200:
        cycling_note = (
            "CRITICAL EXPOSURE TRADE-OFF: While walking or cycling produces 0.0 g CO2/km emissions, vigorous active transit "
            f"in current AQI ({aqi}) increases your respiratory minute ventilation rate by 300-500%, forcing deep "
            "alveolar deposition of fine combustion soot. DO NOT cycle or jog outdoors during severe air episodes; use metro or bus."
        )
    else:
        cycling_note = "Safe for short distances when AQI is below 150. Use dedicated non-motorized lanes away from heavy diesel corridors."

    alternatives.append(
        SustainableAlternative(
            mode="Active Commute (Walking & Cycling)",
            emission_factor_g_co2_per_km=bike_factor,
            estimated_emission_reduction_pct=100.0,
            personal_exposure_mitigation="Zero direct carbon or tailpipe emissions.",
            condition_dependent_note=cycling_note,
        )
    )

    return alternatives


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

    morning_items: List[RecommendationItem] = []
    afternoon_items: List[RecommendationItem] = []
    evening_items: List[RecommendationItem] = []

    # --- MORNING RECOMMENDATIONS ---
    # Morning is typically characterized by surface temperature inversion and stagnant emissions in Indian cities
    if aqi is None:
        morning_items.append(
            RecommendationItem(
                id="rec_morn_aqi_unavailable",
                category="planner",
                title="Hold Strenuous Morning Outdoor Activity",
                time_of_day="morning",
                action="Use an indoor routine until validated AQI is available; do not assume the air is safe.",
                priority="high" if is_vulnerable else "medium",
                reason="Official CPCB AQI could not be established from the available telemetry.",
                supporting_evidence="CPCB data-sufficiency rule requires at least three valid pollutants including PM2.5 or PM10.",
                expected_impact="positive_exposure_reduction",
                limitations="Re-check validated telemetry before resuming outdoor exertion.",
            )
        )
    elif aqi > 200:
        morning_items.append(
            RecommendationItem(
                id="rec_morn_exercise_cancel",
                category="planner",
                title="Shift Morning Workouts Indoors",
                time_of_day="morning",
                action="Avoid outdoor jogging, brisk walking, or sports before 9:00 AM.",
                priority="critical" if is_vulnerable else "high",
                reason="Cool morning ground air traps vehicular exhaust and smoke under a thermal inversion layer.",
                supporting_evidence="CPCB diurnal profiles show peak PM2.5 concentrations occur between 6:00 AM and 8:30 AM in urban centers.",
                expected_impact="positive_exposure_reduction",
                limitations="Requires access to indoor exercise space.",
            )
        )
    elif aqi > 100:
        morning_items.append(
            RecommendationItem(
                id="rec_morn_exercise_moderate",
                category="planner",
                title="Moderate Intensity Morning Routine",
                time_of_day="morning",
                action="Keep workouts to light intensity and conclude before heavy morning traffic begins.",
                priority="medium",
                reason="Moderate particulate levels warrant avoiding heavy cardiac/respiratory exertion outdoors.",
                supporting_evidence="Exercise increases respiration volume from 6 L/min to over 40 L/min.",
                expected_impact="positive_exposure_reduction",
            )
        )
    else:
        morning_items.append(
            RecommendationItem(
                id="rec_morn_clean_air",
                category="planner",
                title="Favorable Morning Air Window",
                time_of_day="morning",
                action="Take advantage of acceptable morning air quality for outdoor walking, exercise, or natural home airing.",
                priority="low" if not is_vulnerable else "medium",
                reason="Current ambient particulate levels are within national ambient standards.",
                supporting_evidence="National Ambient Air Quality Standards (NAAQS) compliance threshold.",
                expected_impact="balanced",
            )
        )

    # Vulnerability check for school children
    if profile.has_children:
        if aqi is None:
            morning_items.append(
                RecommendationItem(
                    id="rec_morn_school_unknown",
                    category="protective",
                    title="Confirm AQI Before Children's Outdoor Play",
                    time_of_day="morning",
                    action="Keep children's outdoor play optional until validated AQI is available; follow school and official advisories.",
                    priority="high",
                    reason="Children are vulnerable and current air quality has not been validated.",
                    supporting_evidence="WHO guidelines advise reducing children's exposure when air quality is uncertain or degraded.",
                    expected_impact="positive_exposure_reduction",
                )
            )
        elif aqi > 150:
            morning_items.append(
                RecommendationItem(
                    id="rec_morn_school_commute",
                    category="protective",
                    title="Child School Commute Protection",
                    time_of_day="morning",
                    action="Ensure children wear child-sized N95 masks while waiting at bus stops or riding open school vans.",
                    priority="high",
                    reason="Children have narrower airways and breathe more air per kilogram of body weight than adults.",
                    supporting_evidence="World Health Organization (WHO) Guidelines on Air Pollution and Child Health.",
                    expected_impact="positive_exposure_reduction",
                )
            )
        else:
            morning_items.append(
                RecommendationItem(
                    id="rec_morn_school_safe",
                    category="protective",
                    title="Safe Outdoor Play & School Transit",
                    time_of_day="morning",
                    action="Outdoor activities and school recess can proceed normally under current ambient quality.",
                    priority="low",
                    reason="Particulate levels are safe for unrestricted outdoor physical activity for children.",
                    supporting_evidence="WHO Global Air Quality Guidelines.",
                    expected_impact="balanced",
                )
            )

    # Commute suggestion for two-wheeler / bus commuters
    if profile.commute_method in ("two_wheeler", "bus", "walking_cycling"):
        if aqi is None:
            morning_items.append(
                RecommendationItem(
                    id="rec_morn_commute_unknown",
                    category="commute",
                    title="Use Enclosed Transit While AQI Is Unverified",
                    time_of_day="morning",
                    action="Prefer metro or enclosed transport and carry a certified respirator until validated AQI is available.",
                    priority="medium",
                    reason="Roadside exposure cannot be risk-assessed without validated telemetry.",
                    supporting_evidence="Bureau of Indian Standards (BIS) IS 9473 / NIOSH N95 certification standards.",
                    expected_impact="positive_exposure_reduction",
                )
            )
        elif aqi > 100:
            morning_items.append(
                RecommendationItem(
                    id="rec_morn_commute_n95",
                    category="commute",
                    title="Wear Certified N95/FFP2 Respirator During Commute",
                    time_of_day="morning",
                    action="Fasten an authentic N95 respirator mask covering nose and mouth tightly.",
                    priority="high",
                    reason="Cloth and surgical masks do not seal against sub-micron PM2.5 combustion particles.",
                    supporting_evidence="Bureau of Indian Standards (BIS) IS 9473 / NIOSH N95 certification standards.",
                    expected_impact="positive_exposure_reduction",
                )
            )
        else:
            morning_items.append(
                RecommendationItem(
                    id="rec_morn_commute_clear",
                    category="commute",
                    title="Satisfactory Road Commute Conditions",
                    time_of_day="morning",
                    action="Standard daily commute. No specialized respiratory masks required at current ambient levels.",
                    priority="low",
                    reason="Particulate levels are safe for unassisted road transit.",
                    supporting_evidence="CPCB Good/Satisfactory criteria thresholds.",
                    expected_impact="balanced",
                )
            )
    elif profile.commute_method == "car_ac":
        morning_items.append(
            RecommendationItem(
                id="rec_morn_car_recirc",
                category="commute",
                title="Enable In-Cabin Air Recirculation",
                time_of_day="morning",
                action="Set vehicle HVAC system to internal recirculation mode with AC fan on low-to-medium.",
                priority="medium",
                reason="Prevents direct ingress of preceding vehicle diesel exhaust into car cabin.",
                supporting_evidence="Cabin filtration testing shows 60-80% PM2.5 reduction in recirculation mode.",
                expected_impact="positive_exposure_reduction",
            )
        )

    # --- AFTERNOON RECOMMENDATIONS ---
    # Afternoon has maximum solar radiation (ozone peak) and higher mixing boundary layer
    if aqi is None:
        afternoon_items.append(
            RecommendationItem(
                id="rec_aft_aqi_unavailable",
                category="indoor",
                title="Keep Windows Closed Until AQI Is Validated",
                time_of_day="afternoon",
                action="Use mechanical filtration and avoid opening windows for ventilation until validated AQI is available.",
                priority="medium",
                reason="Outdoor pollution levels cannot be verified from the current telemetry.",
                supporting_evidence="CPCB data-sufficiency rule for official AQI computation.",
                expected_impact="positive_exposure_reduction",
            )
        )
    elif aqi > 150:
        afternoon_items.append(
            RecommendationItem(
                id="rec_aft_ozone_awareness",
                category="planner",
                title="Midday Boundary Layer Ventilation Window",
                time_of_day="afternoon",
                action="If domestic indoor air feels stuffy, open opposite windows for 10-15 minutes between 1:00 PM and 3:00 PM.",
                priority="medium",
                reason="Solar heating raises the atmospheric boundary layer, diluting ground-level particulate concentrations.",
                supporting_evidence="Atmospheric boundary layer height reaches maximum diurnal expansion in early afternoon.",
                expected_impact="positive_exposure_reduction",
                limitations="Avoid ventilation if local open waste burning or direct construction dust is visible nearby.",
            )
        )
    else:
        afternoon_items.append(
            RecommendationItem(
                id="rec_aft_ventilation_open",
                category="indoor",
                title="Optimal Afternoon Air Exchange",
                time_of_day="afternoon",
                action="Open windows for cross-ventilation to refresh indoor air and flush out domestic CO2.",
                priority="low",
                reason="Ambient air is clean and solar thermal updrafts disperse localized pollutants.",
                supporting_evidence="Building science ventilation guidelines (ASHRAE 62.1).",
                expected_impact="positive_exposure_reduction",
            )
        )

    if profile.occupation_type == "outdoor" and aqi > 200:
        afternoon_items.append(
            RecommendationItem(
                id="rec_aft_outdoor_worker",
                category="protective",
                title="Scheduled Hydration & Indoor Rest Intervals",
                time_of_day="afternoon",
                action="Take 15-minute breaks in shielded indoor areas every 2 hours and maintain active hydration.",
                priority="high",
                reason="Sustained outdoor occupational breathing during peak ozone and particulate hours stresses the pulmonary epithelium.",
                supporting_evidence="Directorate General of Health Services (DGHS) occupational heat and smog advisories.",
                expected_impact="positive_exposure_reduction",
            )
        )

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
