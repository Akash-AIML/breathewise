import { AQICategory, DataQualityStatus, PollutantType } from "@/types/observation";

export type RiskClassification = "low" | "moderate" | "high" | "very_high" | "severe";

export interface HouseholdProfile {
  has_children: boolean;
  has_elderly: boolean;
  has_respiratory_sensitivity: boolean;
  has_cardiovascular_sensitivity: boolean;
  occupation_type: "indoor" | "outdoor" | "hybrid";
  commute_method:
    | "metro_train"
    | "bus"
    | "car_ac"
    | "two_wheeler"
    | "walking_cycling"
    | "work_from_home";
  exercise_routine: "none" | "morning_outdoor" | "evening_outdoor" | "indoor_gym";
  indoor_ventilation: "natural" | "sealed_ac" | "cross_ventilation";
  has_air_purifier: boolean;
  approximate_budget_inr?: number | null;
  home_area_sqft?: number | null;
}

export interface EnvironmentalAssessment {
  risk_level: RiskClassification;
  aqi?: number | null;
  category?: AQICategory | null;
  dominant_pollutant?: PollutantType | null;
  data_quality: DataQualityStatus;
  confidence: number;
  is_stale: boolean;
  assessment_summary: string;
}

export interface RecommendationItem {
  id: string;
  category: "planner" | "indoor" | "commute" | "sustainability" | "protective";
  title: string;
  time_of_day?: "morning" | "afternoon" | "evening" | "all_day" | null;
  action: string;
  priority: "critical" | "high" | "medium" | "low";
  reason: string;
  supporting_evidence: string;
  expected_impact:
    | "positive_exposure_reduction"
    | "positive_emission_reduction"
    | "balanced";
  limitations?: string | null;
}

export interface IndoorGuidance {
  hepa_sizing_cadr_m3_hr?: number | null;
  hepa_sizing_explanation: string;
  filter_maintenance_tips: string[];
  ventilation_advice: string;
  cooking_smoke_precautions: string[];
  practical_low_cost_precautions: string[];
  houseplant_scientific_disclaimer: string;
}

export interface SustainableAlternative {
  mode: string;
  emission_factor_g_co2_per_km: number;
  estimated_emission_reduction_pct: number;
  personal_exposure_mitigation: string;
  condition_dependent_note?: string | null;
}

export interface PersonalizedPlan {
  environmental_assessment: EnvironmentalAssessment;
  household_profile: HouseholdProfile;
  morning_recommendations: RecommendationItem[];
  afternoon_recommendations: RecommendationItem[];
  evening_recommendations: RecommendationItem[];
  indoor_guidance: IndoorGuidance;
  sustainable_alternatives: SustainableAlternative[];
  generated_at: string;
}

