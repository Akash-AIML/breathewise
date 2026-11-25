from typing import List, Optional

from app.schemas.profile import HouseholdProfile
from app.schemas.recommendation import (
    IndoorGuidance,
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

    # Imported lazily: policy_engine re-exports this module's public API.
    from app.core.policy_engine import calculate_hepa_cadr_m3_hr

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
