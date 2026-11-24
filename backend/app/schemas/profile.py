from typing import Literal, Optional

from pydantic import BaseModel, Field


class HouseholdProfile(BaseModel):
    """
    Household profile capturing optional demographic, vulnerability, and lifestyle
    parameters to drive deterministic air protection policy decisions.
    All sensitive health fields are strictly optional.
    """

    has_children: bool = Field(False, description="Presence of children under 12 years old")
    has_elderly: bool = Field(False, description="Presence of senior citizens over 65 years old")
    has_respiratory_sensitivity: bool = Field(
        False, description="Presence of family members with asthma, COPD, or chronic bronchitis"
    )
    has_cardiovascular_sensitivity: bool = Field(
        False, description="Presence of family members with hypertension, heart disease, or post-stroke"
    )
    occupation_type: Literal["indoor", "outdoor", "hybrid"] = Field(
        "indoor", description="Primary work environment"
    )
    commute_method: Literal[
        "metro_train",
        "bus",
        "car_ac",
        "two_wheeler",
        "walking_cycling",
        "work_from_home",
    ] = Field("metro_train", description="Typical daily commute transport mode")
    exercise_routine: Literal[
        "none", "morning_outdoor", "evening_outdoor", "indoor_gym"
    ] = Field("none", description="Physical workout routine")
    indoor_ventilation: Literal["natural", "sealed_ac", "cross_ventilation"] = Field(
        "natural", description="Primary domestic ventilation method"
    )
    has_air_purifier: bool = Field(False, description="Ownership of domestic mechanical HEPA purifiers")
    approximate_budget_inr: Optional[int] = Field(
        None, ge=0, le=500000, description="Approximate household budget for air quality protective measures (INR)"
    )
    home_area_sqft: Optional[int] = Field(
        600, ge=100, le=10000, description="Estimated home carpet area in square feet for CADR calculations"
    )
