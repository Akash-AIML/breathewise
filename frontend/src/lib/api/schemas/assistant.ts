import { z } from "zod";
import { pollutantTypeSchema } from "./observation";
import { riskClassificationSchema } from "./recommendations";

/** Both grounded LLM replies and deterministic failover replies use this shape. */
export const assistantResponseSchema = z.looseObject({
  answer: z.string(),
  referenced_aqi: z.number().int().nullable().optional(),
  dominant_pollutant: pollutantTypeSchema.nullable().optional(),
  risk_level: riskClassificationSchema,
  approved_actions: z.array(z.string()),
  scientific_rationale: z.string(),
  provider_provenance: z.string().optional(),
  llm_grounded: z.boolean().default(false),
  disclaimer: z.string().optional(),
});
