import math
from typing import Dict, List, Optional, Tuple

from app.schemas.observation import (
    AQICategory,
    DataQualityStatus,
    NormalizedPollutantReading,
    PollutantType,
)

# CPCB Official Breakpoints: List of (B_Lo, B_Hi, I_Lo, I_Hi)
# CO is in mg/m3; all other pollutants are in µg/m3
CPCB_BREAKPOINTS: Dict[PollutantType, List[Tuple[float, float, int, int]]] = {
    PollutantType.PM10: [
        (0.0, 50.0, 0, 50),
        (51.0, 100.0, 51, 100),
        (101.0, 250.0, 101, 200),
        (251.0, 350.0, 201, 300),
        (351.0, 430.0, 301, 400),
        (431.0, 500.0, 401, 500),
    ],
    PollutantType.PM2_5: [
        (0.0, 30.0, 0, 50),
        (31.0, 60.0, 51, 100),
        (61.0, 90.0, 101, 200),
        (91.0, 120.0, 201, 300),
        (121.0, 250.0, 301, 400),
        (251.0, 350.0, 401, 500),
    ],
    PollutantType.NO2: [
        (0.0, 40.0, 0, 50),
        (41.0, 80.0, 51, 100),
        (81.0, 180.0, 101, 200),
        (181.0, 280.0, 201, 300),
        (281.0, 400.0, 301, 400),
        (401.0, 500.0, 401, 500),
    ],
    PollutantType.SO2: [
        (0.0, 40.0, 0, 50),
        (41.0, 80.0, 51, 100),
        (81.0, 380.0, 101, 200),
        (381.0, 800.0, 201, 300),
        (801.0, 1600.0, 301, 400),
        (1601.0, 2000.0, 401, 500),
    ],
    PollutantType.CO: [
        (0.0, 1.0, 0, 50),
        (1.1, 2.0, 51, 100),
        (2.1, 10.0, 101, 200),
        (10.1, 17.0, 201, 300),
        (17.1, 34.0, 301, 400),
        (34.1, 50.0, 401, 500),
    ],
    PollutantType.O3: [
        (0.0, 50.0, 0, 50),
        (51.0, 100.0, 51, 100),
        (101.0, 168.0, 101, 200),
        (169.0, 208.0, 201, 300),
        (209.0, 748.0, 301, 400),
        (749.0, 1000.0, 401, 500),
    ],
    PollutantType.NH3: [
        (0.0, 200.0, 0, 50),
        (201.0, 400.0, 51, 100),
        (401.0, 800.0, 101, 200),
        (801.0, 1200.0, 201, 300),
        (1201.0, 1800.0, 301, 400),
        (1801.0, 2400.0, 401, 500),
    ],
    PollutantType.PB: [
        (0.0, 0.5, 0, 50),
        (0.6, 1.0, 51, 100),
        (1.1, 2.0, 101, 200),
        (2.1, 3.0, 201, 300),
        (3.1, 3.5, 301, 400),
        (3.6, 5.0, 401, 500),
    ],
}


def calculate_sub_index(pollutant: PollutantType, concentration: float) -> Optional[int]:
    """Calculate the CPCB sub-index for a single pollutant using linear interpolation."""
    if concentration < 0.0 or math.isnan(concentration):
        return None

    breakpoints = CPCB_BREAKPOINTS.get(pollutant)
    if not breakpoints:
        return None

    # Check each bracket
    for b_lo, b_hi, i_lo, i_hi in breakpoints:
        if b_lo <= concentration <= b_hi:
            sub_index = ((i_hi - i_lo) / (b_hi - b_lo)) * (concentration - b_lo) + i_lo
            return round(sub_index)

    # If concentration exceeds highest bracket, cap sub-index at 500 (Severe tier)
    highest_b_hi = breakpoints[-1][1]
    if concentration > highest_b_hi:
        return 500

    return None


def get_aqi_category(aqi_value: int) -> AQICategory:
    """Map AQI value to official CPCB category."""
    if aqi_value <= 50:
        return AQICategory.GOOD
    elif aqi_value <= 100:
        return AQICategory.SATISFACTORY
    elif aqi_value <= 200:
        return AQICategory.MODERATE
    elif aqi_value <= 300:
        return AQICategory.POOR
    elif aqi_value <= 400:
        return AQICategory.VERY_POOR
    else:
        return AQICategory.SEVERE


class AQICalculatorResult:
    def __init__(
        self,
        aqi: Optional[int],
        dominant_pollutant: Optional[PollutantType],
        category: Optional[AQICategory],
        sub_indices: Dict[PollutantType, int],
        data_sufficiency_met: bool,
        quality_status: DataQualityStatus,
        reason: Optional[str] = None,
    ):
        self.aqi = aqi
        self.dominant_pollutant = dominant_pollutant
        self.category = category
        self.sub_indices = sub_indices
        self.data_sufficiency_met = data_sufficiency_met
        self.quality_status = quality_status
        self.reason = reason


def compute_official_cpcb_aqi(
    readings: Dict[PollutantType, NormalizedPollutantReading],
) -> AQICalculatorResult:
    """
    Computes official CPCB AQI adhering strictly to CPCB regulations:
    1. Sub-indices calculated for all available valid criteria pollutants.
    2. Data Sufficiency Rule:
       - Must have valid sub-indices for AT LEAST 3 pollutants.
       - One of the pollutants MUST be PM2.5 or PM10.
    3. Overall AQI = max(sub_indices).
    4. Dominant pollutant = pollutant with the highest sub-index.
    """
    sub_indices: Dict[PollutantType, int] = {}

    for pollutant, reading in readings.items():
        if reading.value is not None and not math.isnan(reading.value) and reading.value >= 0.0:
            si = calculate_sub_index(pollutant, reading.value)
            if si is not None:
                sub_indices[pollutant] = si
                reading.sub_index = si

    # Enforce CPCB Data Sufficiency Rule
    has_particulate = PollutantType.PM2_5 in sub_indices or PollutantType.PM10 in sub_indices
    sufficient_count = len(sub_indices) >= 3

    if not sufficient_count or not has_particulate:
        reasons = []
        if len(sub_indices) < 3:
            reasons.append(
                f"Only {len(sub_indices)} criteria pollutants available (minimum 3 required)"
            )
        if not has_particulate:
            reasons.append("Neither PM2.5 nor PM10 particulate reading is available")
        return AQICalculatorResult(
            aqi=None,
            dominant_pollutant=None,
            category=None,
            sub_indices=sub_indices,
            data_sufficiency_met=False,
            quality_status=DataQualityStatus.INSUFFICIENT,
            reason="; ".join(reasons),
        )

    # Overall AQI is the maximum of the individual sub-indices
    max_pollutant = max(sub_indices, key=lambda k: sub_indices[k])
    overall_aqi = sub_indices[max_pollutant]
    category = get_aqi_category(overall_aqi)

    return AQICalculatorResult(
        aqi=overall_aqi,
        dominant_pollutant=max_pollutant,
        category=category,
        sub_indices=sub_indices,
        data_sufficiency_met=True,
        quality_status=DataQualityStatus.VERIFIED,
        reason=None,
    )
