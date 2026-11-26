import { z } from "zod";
import { aqiCategorySchema, dataQualityStatusSchema, pollutantTypeSchema } from "./observation";

export const riskClassificationSchema = z.enum(["low", "moderate", "high", "very_high", "severe"]);

export const householdProfileSchema = z.looseObject({
  has_children: z.boolean(),
  has_elderly: z.boolean(),
  has_respiratory_sensitivity: z.boolean(),
  has_cardiovascular_sensitivity: z.boolean(),
  occupation_type: z.enum(["indoor", "outdoor", "hybrid"]),
  commute_method: z.enum([
    "metro_train",
    "bus",
    "car_ac",
    "two_wheeler",
    "walking_cycling",
    "work_from_home",
  ]),
  exercise_routine: z.enum(["none", "morning_outdoor", "evening_outdoor", "indoor_gym"]),
  indoor_ventilation: z.enum(["natural", "sealed_ac", "cross_ventilation"]),
  has_air_purifier: z.boolean(),
  approximate_budget_inr: z.number().finite().nullable().optional(),
  home_area_sqft: z.number().finite().nullable().optional(),
});

export const environmentalAssessmentSchema = z.looseObject({
  risk_level: riskClassificationSchema,
  aqi: z.number().int().nullable().optional(),
  category: aqiCategorySchema.nullable().optional(),
  dominant_pollutant: pollutantTypeSchema.nullable().optional(),
  data_quality: dataQualityStatusSchema,
  confidence: z.number().finite().min(0).max(1),
  is_stale: z.boolean().default(false),
  assessment_summary: z.string(),
});

export const recommendationItemSchema = z.looseObject({
  id: z.string(),
  category: z.enum(["planner", "indoor", "commute", "sustainability", "protective"]),
  title: z.string(),
  time_of_day: z.enum(["morning", "afternoon", "evening", "all_day"]).nullable().optional(),
  action: z.string(),
  priority: z.enum(["critical", "high", "medium", "low"]),
  reason: z.string(),
  supporting_evidence: z.string(),
  expected_impact: z.enum([
    "positive_exposure_reduction",
    "positive_emission_reduction",
    "balanced",
  ]),
  limitations: z.string().nullable().optional(),
});

export const indoorGuidanceSchema = z.looseObject({
  hepa_sizing_cadr_m3_hr: z.number().int().nullable().optional(),
  hepa_sizing_explanation: z.string(),
  filter_maintenance_tips: z.array(z.string()),
  ventilation_advice: z.string(),
  cooking_smoke_precautions: z.array(z.string()),
  practical_low_cost_precautions: z.array(z.string()),
  houseplant_scientific_disclaimer: z.string(),
});

export const sustainableAlternativeSchema = z.looseObject({
  mode: z.string(),
  emission_factor_g_co2_per_km: z.number().finite(),
  estimated_emission_reduction_pct: z.number().finite(),
  personal_exposure_mitigation: z.string(),
  condition_dependent_note: z.string().nullable().optional(),
});

export const personalizedPlanSchema = z.looseObject({
  environmental_assessment: environmentalAssessmentSchema,
  household_profile: householdProfileSchema,
  morning_recommendations: z.array(recommendationItemSchema),
  afternoon_recommendations: z.array(recommendationItemSchema),
  evening_recommendations: z.array(recommendationItemSchema),
  indoor_guidance: indoorGuidanceSchema,
  sustainable_alternatives: z.array(sustainableAlternativeSchema),
  generated_at: z.string().min(1),
});
