import { z } from "zod";

export const geocodedLocationSchema = z.looseObject({
  id: z.number().int(),
  name: z.string(),
  latitude: z.number().finite().min(-90).max(90),
  longitude: z.number().finite().min(-180).max(180),
  admin1: z.string().optional(),
  country: z.string().optional(),
});

export const locationSearchResponseSchema = z.looseObject({
  results: z.array(geocodedLocationSchema).default([]),
});

export const reverseGeocodedPlaceSchema = z.looseObject({
  name: z.string(),
  state: z.string().nullable().optional(),
  country: z.string().nullable().optional(),
  display_name: z.string().nullable().optional(),
  source: z.string(),
});

export const reverseGeocodeResponseSchema = z.looseObject({
  place: reverseGeocodedPlaceSchema.nullable(),
});
