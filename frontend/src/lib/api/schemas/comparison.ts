import { z } from "zod";
import { observationSchema } from "./observation";

export const comparisonBasisSchema = z.enum(["live_station", "coordinate_estimate", "mixed"]);

export const comparisonDifferentialSchema = z.looseObject({
  cleanest_station_id: z.string().nullable().optional(),
  cleanest_station_name: z.string().nullable().optional(),
  most_polluted_station_id: z.string().nullable().optional(),
  most_polluted_station_name: z.string().nullable().optional(),
  aqi_difference: z.number().int().nullable().optional(),
  pm25_difference_ug_m3: z.number().finite().nullable().optional(),
  summary: z.string(),
});

export const comparisonCandidateSchema = z.looseObject({
  id: z.string(),
  label: z.string(),
  city: z.string().nullable().optional(),
  state: z.string().nullable().optional(),
  latitude: z.number().finite().min(-90).max(90),
  longitude: z.number().finite().min(-180).max(180),
  basis: z.enum(["live_station", "coordinate_estimate"]),
  source: z.string(),
});

export const comparisonPresetSchema = z.looseObject({
  key: z.string(),
  name: z.string(),
  description: z.string(),
  ids: z.array(z.string()),
  basis: z.enum(["live_station", "coordinate_estimate"]),
  source: z.string(),
  candidates: z.array(comparisonCandidateSchema).default([]),
});

export const comparisonPresetsResponseSchema = z.looseObject({
  success: z.boolean().default(true),
  source: z.string().default("unknown"),
  presets: z.array(comparisonPresetSchema).default([]),
  message: z.string().default(""),
});

export const comparisonResponseSchema = z.looseObject({
  success: z.boolean().default(true),
  stations_count: z.number().int().nonnegative(),
  observations: z.array(observationSchema).default([]),
  differential: comparisonDifferentialSchema.nullable().optional(),
  basis: comparisonBasisSchema.default("mixed"),
  source: z.string().default("unknown"),
  requested_ids: z.array(z.string()).default([]),
  unresolved_ids: z.array(z.string()).default([]),
  message: z.string().default(""),
});
