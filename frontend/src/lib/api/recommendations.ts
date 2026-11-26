import { z } from "zod";
import {
  HouseholdProfile,
  IndoorGuidance,
  PersonalizedPlan,
  SustainableAlternative,
} from "@/types/recommendations";
import { apiUrl, ApiError, fetchWithTimeout, parseApiResponse, safeErrorMessage } from "./client";
import {
  indoorGuidanceSchema,
  personalizedPlanSchema,
  sustainableAlternativeSchema,
} from "./schemas/recommendations";

export async function fetchPersonalizedPlan(
  lat: number,
  lon: number,
  profile: HouseholdProfile
): Promise<PersonalizedPlan> {
  return fetchWithTimeout(
    apiUrl("/api/v1/recommendations/plan"),
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ lat, lon, profile }),
    },
    async (response) => {
      if (!response.ok) {
        throw new ApiError(
          safeErrorMessage("Failed to generate personalized plan.", response.status),
          response.status
        );
      }
      return parseApiResponse(response, personalizedPlanSchema, "Failed to generate personalized plan.");
    }
  );
}

export async function fetchIndoorGuidance(
  areaSqft: number = 600,
  aqi?: number
): Promise<IndoorGuidance> {
  const url = new URL(apiUrl("/api/v1/recommendations/indoor"));
  url.searchParams.append("area_sqft", areaSqft.toString());
  if (aqi !== undefined) {
    url.searchParams.append("aqi", aqi.toString());
  }

  return fetchWithTimeout(
    url.toString(),
    {
      method: "GET",
      headers: { Accept: "application/json" },
    },
    async (response) => {
      if (!response.ok) {
        throw new ApiError("Failed to fetch indoor guidance.", response.status);
      }
      return parseApiResponse(response, indoorGuidanceSchema, "Failed to fetch indoor guidance.");
    }
  );
}

export async function fetchSustainableAlternatives(
  aqi?: number
): Promise<SustainableAlternative[]> {
  const url = new URL(apiUrl("/api/v1/recommendations/sustainable-alternatives"));
  if (aqi !== undefined) {
    url.searchParams.append("aqi", aqi.toString());
  }

  return fetchWithTimeout(
    url.toString(),
    {
      method: "GET",
      headers: { Accept: "application/json" },
    },
    async (response) => {
      if (!response.ok) {
        throw new ApiError("Failed to fetch sustainable alternatives.", response.status);
      }
      return parseApiResponse(
        response,
        z.array(sustainableAlternativeSchema),
        "Failed to fetch sustainable alternatives."
      );
    }
  );
}
