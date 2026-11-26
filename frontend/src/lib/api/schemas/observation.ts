import { z } from "zod";

export const pollutantTypeSchema = z.enum(["PM2.5", "PM10", "NO2", "SO2", "CO", "O3", "NH3", "Pb"]);

export const aqiCategorySchema = z.enum([
  "Good",
  "Satisfactory",
  "Moderate",
  "Poor",
  "Very Poor",
  "Severe",
]);

export const dataQualityStatusSchema = z.enum([
  "verified",
  "estimated",
  "delayed",
  "insufficient",
  "stale",
  "unavailable",
]);

export const pollutantReadingSchema = z.looseObject({
  pollutant: pollutantTypeSchema,
  value: z.number().finite().nonnegative(),
  // Backend omits the unit when the provider does not report one; normalize
  // that to the interface's explicit null instead of an optional property.
  unit: z.string().nullable().default(null),
  sub_index: z.number().int().nonnegative().nullable().optional(),
  averaging_period_hours: z.number().int().min(1).max(24).nullable().optional(),
  min_value: z.number().finite().nonnegative().nullable().optional(),
  max_value: z.number().finite().nonnegative().nullable().optional(),
  source_pollutant_id: z.string().nullable().optional(),
});

export const hourlyTrendPointSchema = z.looseObject({
  time: z.string().min(1),
  pm2_5: z.number().finite().nullable().optional(),
  pm10: z.number().finite().nullable().optional(),
  no2: z.number().finite().nullable().optional(),
  so2: z.number().finite().nullable().optional(),
  co: z.number().finite().nullable().optional(),
  o3: z.number().finite().nullable().optional(),
  aqi: z.number().int().nullable().optional(),
  category: aqiCategorySchema.nullable().optional(),
});

export const stationMetadataSchema = z.looseObject({
  station_id: z.string(),
  station_name: z.string(),
  city: z.string(),
  state: z.string(),
  latitude: z.number().finite().min(-90).max(90),
  longitude: z.number().finite().min(-180).max(180),
  distance_km: z.number().finite().nonnegative().nullable().optional(),
  elevation_m: z.number().finite().nullable().optional(),
  provider: z.string().nullable().optional(),
  source_observation_time: z.string().nullable().optional(),
});

export const observationSchema = z.looseObject({
  provider: z.string().min(1),
  station: stationMetadataSchema,
  readings: z.record(z.string(), pollutantReadingSchema),
  calculated_aqi: z.number().int().nonnegative().nullable().optional(),
  dominant_pollutant: pollutantTypeSchema.nullable().optional(),
  aqi_category: aqiCategorySchema.nullable().optional(),
  data_sufficiency_met: z.boolean(),
  measurement_timestamp: z.string().min(1),
  retrieval_timestamp: z.string().min(1),
  data_quality_status: dataQualityStatusSchema,
  notes: z.string().nullable().optional(),
  hourly_trend: z.array(hourlyTrendPointSchema).optional().default([]),
});

export const airQualityResponseSchema = z.looseObject({
  success: z.boolean(),
  data: observationSchema.nullable().optional().default(null),
  message: z.string().nullable().optional(),
});

export const stationsResponseSchema = z.looseObject({
  success: z.boolean(),
  count: z.number().int().nonnegative(),
  data: z.array(stationMetadataSchema),
  message: z.string().nullable().optional(),
});
