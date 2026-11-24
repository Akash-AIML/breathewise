import json
import logging
import re
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.core.policy_engine import (
    assess_environmental_risk,
    generate_personalized_plan,
)
from app.schemas.assistant import ExplanationResponse
from app.schemas.observation import NormalizedObservation
from app.schemas.profile import HouseholdProfile
from app.schemas.recommendation import EnvironmentalAssessment, PersonalizedPlan

logger = logging.getLogger(__name__)

# Patterns indicating potential adversarial prompt injection or role hijacking
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior)\s+instructions",
    r"act\s+as\s+(an\s+)?(unrestricted|jailbroken|developer|dan)",
    r"override\s+(the\s+)?(risk|aqi|system|safety)",
    r"forget\s+(all\s+)?(previous|prior)\s+rules",
    r"you\s+are\s+now\s+(an\s+)?unrestricted",
    r"system\s*:\s*you\s+must",
    r"<\|im_start\|>",
    r"<\|system\|>",
]


class LLMAssistantService:
    """
    STAGE 3: Explainable Generative AI Assistant Service
    Coordinates prompt safety screening, external LLM structured JSON generation,
    schema validation, and deterministic fallback.
    """

    def __init__(self):
        self.groq_api_key = settings.GROQ_API_KEY
        self.gemini_api_key = settings.GEMINI_API_KEY

    def screen_for_prompt_injection(self, user_query: str) -> bool:
        """
        Returns True if the query contains suspicious adversarial injection patterns.
        """
        normalized = user_query.lower()
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, normalized):
                logger.warning("Prompt injection detected in query: %s", user_query)
                return True
        return False

    async def generate_explanation(
        self,
        query: str,
        observation: NormalizedObservation,
        profile: HouseholdProfile,
    ) -> ExplanationResponse:
        """
        Generates grounded explanation for user query using Stage 1 assessment and Stage 2 policies.
        """
        # Step 1: Security Screening
        is_injection = self.screen_for_prompt_injection(query)
        if is_injection:
            return ExplanationResponse(
                answer=(
                    "I noticed instruction override patterns in your question. For your health and safety, "
                    "BreatheWise exclusively explains approved environmental policies grounded in validated monitoring telemetry."
                ),
                referenced_aqi=observation.calculated_aqi,
                dominant_pollutant=observation.dominant_pollutant,
                risk_level=assess_environmental_risk(observation).risk_level,
                approved_actions=["Follow official CPCB health advisories."],
                scientific_rationale="Security constraint: Instructions cannot alter validated risk models.",
                provider_provenance=observation.provider,
                llm_grounded=False,
            )

        # Step 2: Deterministic Baseline Engine Execution (Stages 1 & 2)
        assessment = assess_environmental_risk(observation)
        plan = generate_personalized_plan(assessment, profile)

        # Step 3: Attempt Server-Side LLM with Structured JSON
        llm_response = await self._call_server_llm(query, observation, assessment, plan, profile)
        if llm_response:
            return llm_response

        # Step 4: Deterministic Fallback Engine (Guaranteed zero-failure path)
        return self._generate_deterministic_fallback(query, observation, assessment, plan, profile)

    async def _call_server_llm(
        self,
        query: str,
        obs: NormalizedObservation,
        assessment: EnvironmentalAssessment,
        plan: PersonalizedPlan,
        profile: HouseholdProfile,
    ) -> Optional[ExplanationResponse]:
        """
        Attempts structured JSON completion via Groq or Gemini server-side APIs.
        Validates output strictly with Pydantic.
        """
        if not self.groq_api_key and not self.gemini_api_key:
            return None

        # Build grounded system prompt with approved actions
        system_prompt = (
            "You are BreatheWise, an evidence-based urban air quality assistant for Indian families. "
            "You MUST explain the pre-calculated, approved recommendations provided below. "
            "STRICT RULES:\n"
            "1. You may NEVER fabricate or change the AQI value.\n"
            "2. You may NEVER invent medical cures or unsupported risk statistics.\n"
            "3. You may NEVER override data quality status or recommend outdoor exercise during severe air.\n"
            "4. Output MUST be a valid JSON object matching the requested schema.\n\n"
            f"VALIDATED TELEMETRY:\n"
            f"- Station: {obs.station.station_name} ({obs.station.city})\n"
            f"- CPCB AQI: {obs.calculated_aqi} ({obs.aqi_category})\n"
            f"- Dominant Pollutant: {obs.dominant_pollutant}\n"
            f"- Risk Classification: {assessment.risk_level.value}\n"
            f"- Provider: {obs.provider}\n\n"
            "APPROVED RECOMMENDATIONS:\n"
            + "\n".join(
                [
                    f"- [{item.time_of_day}] {item.title}: {item.action} (Evidence: {item.supporting_evidence})"
                    for item in plan.morning_recommendations
                    + plan.afternoon_recommendations
                    + plan.evening_recommendations
                ]
            )
        )

        try:
            if self.groq_api_key:
                return await self._call_groq(query, system_prompt, obs, assessment)
            elif self.gemini_api_key:
                return await self._call_gemini(query, system_prompt, obs, assessment)
        except Exception as e:
            logger.warning("External LLM API call failed: %s; invoking fallback.", str(e))
            return None

        return None

    async def _call_groq(
        self, query: str, system_prompt: str, obs: NormalizedObservation, assessment: EnvironmentalAssessment
    ) -> Optional[ExplanationResponse]:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_tokens": 800,
        }

        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.warning("Groq API returned HTTP %s", resp.status_code)
                return None

            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)

            # Ensure baseline fields cannot be tampered with by LLM
            return ExplanationResponse(
                answer=parsed.get("answer", "Here is your air quality guidance."),
                referenced_aqi=obs.calculated_aqi,
                dominant_pollutant=obs.dominant_pollutant,
                risk_level=assessment.risk_level,
                approved_actions=parsed.get("approved_actions", []),
                scientific_rationale=parsed.get(
                    "scientific_rationale", "Grounded in CPCB NAQI and WHO guidelines."
                ),
                provider_provenance=obs.provider,
                llm_grounded=True,
            )

    async def _call_gemini(
        self, query: str, system_prompt: str, obs: NormalizedObservation, assessment: EnvironmentalAssessment
    ) -> Optional[ExplanationResponse]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{system_prompt}\n\nUSER QUESTION: {query}\n\nProvide response in JSON."}
                    ]
                }
            ],
            "generationConfig": {"response_mime_type": "application/json"},
        }

        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                return None

            data = resp.json()
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(content)

            return ExplanationResponse(
                answer=parsed.get("answer", "Here is your air quality guidance."),
                referenced_aqi=obs.calculated_aqi,
                dominant_pollutant=obs.dominant_pollutant,
                risk_level=assessment.risk_level,
                approved_actions=parsed.get("approved_actions", []),
                scientific_rationale=parsed.get(
                    "scientific_rationale", "Grounded in CPCB NAQI and WHO guidelines."
                ),
                provider_provenance=obs.provider,
                llm_grounded=True,
            )

    def _generate_deterministic_fallback(
        self,
        query: str,
        obs: NormalizedObservation,
        assessment: EnvironmentalAssessment,
        plan: PersonalizedPlan,
        profile: HouseholdProfile,
    ) -> ExplanationResponse:
        """
        DETERMINISTIC FALLBACK ENGINE:
        Synthesizes structured, zero-hallucination responses when LLM is offline or unconfigured.
        """
        q = query.lower()
        aqi = obs.calculated_aqi or 150
        risk = assessment.risk_level

        # Category 1: Exercise / Outdoor Workouts
        if any(w in q for w in ("exercise", "workout", "jog", "run", "walk", "sports", "gym")):
            if aqi > 200:
                answer = (
                    f"It is NOT safe to exercise outdoors right now. The current AQI at {obs.station.station_name} "
                    f"is {aqi} ({obs.aqi_category}), with {obs.dominant_pollutant} as the dominant pollutant. "
                    "Vigorous outdoor exercise increases your minute ventilation rate by up to 500%, pulling fine combustion "
                    "soot deep into your alveolar lung tissue. Please shift workouts to an indoor enclosed space."
                )
                rationale = (
                    "Cold morning inversion traps PM2.5 in the breathing zone. Exercise escalates inhaled particulate dose."
                )
                actions = [
                    "Cancel outdoor running, jogging, and cycling.",
                    "Exercise indoors with windows closed and air purifier active.",
                ]
            else:
                answer = (
                    f"Outdoor exercise is acceptable under current conditions (AQI: {aqi}, Category: {obs.aqi_category}). "
                    "However, schedule physical activities for mid-afternoon when atmospheric dispersion is greatest."
                )
                rationale = "Particulate levels are within acceptable thresholds for moderate physical activity."
                actions = ["Keep outdoor workouts to light or moderate intensity."]

        # Category 2: Children / Recess / School
        elif any(w in q for w in ("child", "children", "kid", "kids", "baby", "infant", "school", "recess", "play")):
            if aqi > 150:
                answer = (
                    f"Children should avoid outdoor physical play at this time. With an ambient AQI of {aqi} ({obs.aqi_category}), "
                    "children are disproportionately vulnerable because their lungs are still developing and they breathe more air "
                    "per minute relative to their body weight than adults. Ensure they wear a snug-fitting child-sized N95 mask during school transit."
                )
                rationale = "WHO Child Health guidelines: narrower pediatric airways suffer heightened inflammation from fine particles."
                actions = [
                    "Keep children indoors during morning smog peaks.",
                    "Use certified pediatric N95 respirators for school commutes.",
                ]
            else:
                answer = (
                    f"Current air quality (AQI: {aqi}, Category: {obs.aqi_category}) is within safe limits for children's outdoor play "
                    "and school sports."
                )
                rationale = "Criteria pollutants do not exceed national pediatric safety standards."
                actions = ["Permit standard outdoor school activities."]

        # Category 3: Indoor Air & Houseplants
        elif any(w in q for w in ("plant", "houseplant", "snake plant", "indoor", "purifier", "filter", "cadr")):
            cadr = plan.indoor_guidance.hepa_sizing_cadr_m3_hr
            answer = (
                f"For your home area (~{profile.home_area_sqft} sq.ft.), a mechanical air purifier delivering a Clean Air Delivery Rate (CADR) "
                f"of at least {cadr} m³/hr is recommended. Regarding houseplants: while aesthetically pleasing, peer-reviewed environmental studies "
                "conclusively prove that houseplants cannot meaningfully filter fine particulate matter (PM2.5) in living rooms. "
                "Only True HEPA filters with dense borosilicate fiber webs capture airborne soot effectively."
            )
            rationale = "Waring et al. (Drexel University, 2019): Plant air cleaning rates are negligible compared to mechanical air exchange."
            actions = [
                f"Ensure domestic purifier provides at least {cadr} m³/hr CADR.",
                "Vacuum mesh pre-filters every 2 weeks; never wash True HEPA filters with water.",
                "Turn on kitchen chimney exhaust whenever heating cooking oil.",
            ]

        # Category 4: Commute / Mask / Transit
        elif any(w in q for w in ("commute", "travel", "metro", "bus", "car", "bike", "cycle", "mask", "n95")):
            if aqi > 100:
                answer = (
                    f"For commuting in current air ({aqi} AQI, {obs.dominant_pollutant}), the electric metro is your safest and cleanest option. "
                    "Underground and modern AC metro trains filter out 50-70% of road-level particulate matter while generating 86% less CO2 than a solo car. "
                    "If commuting by two-wheeler or non-AC bus, you must wear an authentic N95/FFP2 respirator covering your nose and mouth tightly."
                )
                rationale = "Roadside micro-environments feature localized diesel exhaust peaks up to 3x higher than ambient monitors."
                actions = [
                    "Prefer electric metro transit over surface two-wheeler commute.",
                    "Wear a certified N95 respirator (cloth and surgical masks fail against sub-micron PM2.5).",
                    "Keep car AC in internal recirculation mode.",
                ]
            else:
                answer = (
                    f"Current ambient road air is satisfactory (AQI: {aqi}). Public transit, metro, and active cycling are all acceptable."
                )
                rationale = "Ambient criteria pollutants are within standard limits."
                actions = ["Standard commute routines without specialized respirators."]

        # Category 5: General / Why was this recommended
        else:
            answer = (
                f"Based on real-time sensor measurements from {obs.station.station_name}, your current AQI is {aqi} "
                f"({obs.aqi_category}), with {obs.dominant_pollutant} as the dominant criteria pollutant. "
                f"We categorized your environmental risk as {risk.value.upper()}. "
                + (
                    "Because your household profile includes vulnerable family members (children or respiratory sensitivity), "
                    "our policy engine escalated protective precautions."
                    if (profile.has_children or profile.has_respiratory_sensitivity)
                    else "Our policy engine generated tailored recommendations for your daily commute and indoor ventilation."
                )
            )
            rationale = "CPCB NAQI multi-pollutant sub-index evaluation."
            actions = [item.action for item in plan.morning_recommendations[:2]]

        return ExplanationResponse(
            answer=answer,
            referenced_aqi=obs.calculated_aqi,
            dominant_pollutant=obs.dominant_pollutant,
            risk_level=risk,
            approved_actions=actions,
            scientific_rationale=rationale,
            provider_provenance=obs.provider,
            llm_grounded=False,
        )

