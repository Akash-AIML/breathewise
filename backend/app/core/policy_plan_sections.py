from app.core.aqi_calculator import (
    AQI_MODERATE_MAX,
    AQI_SATISFACTORY_MAX,
    VULNERABLE_AQI_THRESHOLD,
)
from app.schemas.profile import HouseholdProfile
from app.schemas.recommendation import RecommendationItem


def _morning_activity_item(aqi: int | None, is_vulnerable: bool) -> RecommendationItem:
    if aqi is None:
        return RecommendationItem(
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
    if aqi > AQI_MODERATE_MAX:
        return RecommendationItem(
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
    if aqi > AQI_SATISFACTORY_MAX:
        return RecommendationItem(
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
    return RecommendationItem(
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


def _morning_children_item(aqi: int | None) -> RecommendationItem:
    if aqi is None:
        return RecommendationItem(
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
    if aqi > VULNERABLE_AQI_THRESHOLD:
        return RecommendationItem(
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
    return RecommendationItem(
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


def _build_morning_recommendations(
    aqi: int | None, profile: HouseholdProfile, is_vulnerable: bool
) -> list[RecommendationItem]:
    morning_items: list[RecommendationItem] = [_morning_activity_item(aqi, is_vulnerable)]
    if profile.has_children:
        morning_items.append(_morning_children_item(aqi))

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
        elif aqi > AQI_SATISFACTORY_MAX:
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

    return morning_items


def _build_afternoon_recommendations(
    aqi: int | None, profile: HouseholdProfile
) -> list[RecommendationItem]:
    afternoon_items: list[RecommendationItem] = []

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
    elif aqi > VULNERABLE_AQI_THRESHOLD:
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

    if profile.occupation_type == "outdoor" and aqi is not None and aqi > AQI_MODERATE_MAX:
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

    return afternoon_items
