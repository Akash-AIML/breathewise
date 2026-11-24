from app.core.aqi_calculator import (
    calculate_sub_index,
    compute_official_cpcb_aqi,
    get_aqi_category,
)
from app.schemas.observation import (
    AQICategory,
    DataQualityStatus,
    NormalizedPollutantReading,
    PollutantType,
)


def test_sub_index_linear_interpolation():
    # PM2.5 = 45 µg/m³
    # Breakpoint bracket: (31.0, 60.0, 51, 100)
    # Expected: ((100 - 51) / (60 - 31)) * (45 - 31) + 51 = (49 / 29) * 14 + 51 = 23.655 + 51 = 74.655 -> 75
    si = calculate_sub_index(PollutantType.PM2_5, 45.0)
    assert si == 75

    # PM10 = 35 µg/m³ (0-50 bracket, 1:1 ratio)
    si_pm10 = calculate_sub_index(PollutantType.PM10, 35.0)
    assert si_pm10 == 35

    # CO = 5.0 mg/m³
    # Breakpoint bracket: (2.1, 10.0, 101, 200)
    # Expected: ((200 - 101) / (10.0 - 2.1)) * (5.0 - 2.1) + 101 = (99 / 7.9) * 2.9 + 101 = 36.34 + 101 = 137.34 -> 137
    si_co = calculate_sub_index(PollutantType.CO, 5.0)
    assert si_co == 137


def test_aqi_categories_mapping():
    assert get_aqi_category(40) == AQICategory.GOOD
    assert get_aqi_category(50) == AQICategory.GOOD
    assert get_aqi_category(85) == AQICategory.SATISFACTORY
    assert get_aqi_category(100) == AQICategory.SATISFACTORY
    assert get_aqi_category(160) == AQICategory.MODERATE
    assert get_aqi_category(200) == AQICategory.MODERATE
    assert get_aqi_category(250) == AQICategory.POOR
    assert get_aqi_category(300) == AQICategory.POOR
    assert get_aqi_category(360) == AQICategory.VERY_POOR
    assert get_aqi_category(400) == AQICategory.VERY_POOR
    assert get_aqi_category(450) == AQICategory.SEVERE
    assert get_aqi_category(500) == AQICategory.SEVERE


def test_cpcb_data_sufficiency_rejection_fewer_than_3_pollutants():
    # Only 2 pollutants provided (PM2.5 and PM10)
    readings = {
        PollutantType.PM2_5: NormalizedPollutantReading(
            pollutant=PollutantType.PM2_5, value=25.0, unit="µg/m³"
        ),
        PollutantType.PM10: NormalizedPollutantReading(
            pollutant=PollutantType.PM10, value=45.0, unit="µg/m³"
        ),
    }
    result = compute_official_cpcb_aqi(readings)
    assert result.data_sufficiency_met is False
    assert result.aqi is None
    assert result.category is None
    assert result.quality_status == DataQualityStatus.INSUFFICIENT
    assert "minimum 3 required" in result.reason


def test_cpcb_data_sufficiency_rejection_no_particulate():
    # 3 gaseous pollutants provided, but NO PM2.5 or PM10
    readings = {
        PollutantType.NO2: NormalizedPollutantReading(
            pollutant=PollutantType.NO2, value=45.0, unit="µg/m³"
        ),
        PollutantType.SO2: NormalizedPollutantReading(
            pollutant=PollutantType.SO2, value=30.0, unit="µg/m³"
        ),
        PollutantType.CO: NormalizedPollutantReading(
            pollutant=PollutantType.CO, value=1.5, unit="mg/m³"
        ),
    }
    result = compute_official_cpcb_aqi(readings)
    assert result.data_sufficiency_met is False
    assert result.aqi is None
    assert result.quality_status == DataQualityStatus.INSUFFICIENT
    assert "Neither PM2.5 nor PM10" in result.reason


def test_cpcb_valid_calculation_satisfactory():
    # Valid 3 pollutants with PM2.5
    readings = {
        PollutantType.PM2_5: NormalizedPollutantReading(
            pollutant=PollutantType.PM2_5, value=45.0, unit="µg/m³"
        ),
        PollutantType.NO2: NormalizedPollutantReading(
            pollutant=PollutantType.NO2, value=35.0, unit="µg/m³"
        ),
        PollutantType.CO: NormalizedPollutantReading(
            pollutant=PollutantType.CO, value=0.8, unit="mg/m³"
        ),
    }
    result = compute_official_cpcb_aqi(readings)
    assert result.data_sufficiency_met is True
    assert result.quality_status == DataQualityStatus.VERIFIED
    # PM2.5 sub-index is 75, which is highest
    assert result.dominant_pollutant == PollutantType.PM2_5
    assert result.aqi == 75
    assert result.category == AQICategory.SATISFACTORY


def test_cpcb_severe_tier_capping():
    # Extreme PM2.5 of 450 µg/m³ (exceeds highest 350 breakpoint)
    readings = {
        PollutantType.PM2_5: NormalizedPollutantReading(
            pollutant=PollutantType.PM2_5, value=450.0, unit="µg/m³"
        ),
        PollutantType.PM10: NormalizedPollutantReading(
            pollutant=PollutantType.PM10, value=550.0, unit="µg/m³"
        ),
        PollutantType.NO2: NormalizedPollutantReading(
            pollutant=PollutantType.NO2, value=250.0, unit="µg/m³"
        ),
    }
    result = compute_official_cpcb_aqi(readings)
    assert result.data_sufficiency_met is True
    assert result.aqi == 500
    assert result.category == AQICategory.SEVERE
