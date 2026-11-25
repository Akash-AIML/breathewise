import asyncio
import logging
from typing import Optional

# Retained as the monkeypatch target used by the provider failover tests.
import httpx  # noqa: F401

from app.core.config import settings
from app.core.policy_engine import (
    assess_environmental_risk,
    generate_personalized_plan,
)
from app.schemas.assistant import ExplanationResponse
from app.schemas.observation import NormalizedObservation
from app.schemas.profile import HouseholdProfile
from app.schemas.recommendation import EnvironmentalAssessment, PersonalizedPlan
from app.services import llm_safety
from app.services.deterministic_assistant import (
    generate_deterministic_fallback,
    render_label,
)
from app.services.llm_providers import (
    _LLMPermanentError,
    call_gemini,
    call_groq,
)
from app.services.llm_providers import (
    parse_json_object as _parse_json_object,
)

logger = logging.getLogger(__name__)

# Re-exported from their new home to keep the pre-split module paths working.
INJECTION_MARKERS = llm_safety.INJECTION_MARKERS
INJECTION_PATTERNS = llm_safety.INJECTION_PATTERNS
normalize_for_screening = llm_safety.normalize_for_screening


class LLMAssistantService:
    """
    STAGE 3: Explainable Generative AI Assistant Service
    Coordinates prompt safety screening, external LLM structured JSON generation,
    schema validation, and deterministic fallback.
    """

    def __init__(self):
        self.groq_api_key = settings.GROQ_API_KEY
        self.gemini_api_key = settings.GEMINI_API_KEY

    @staticmethod
    def _gemini_model_chain() -> list[str]:
        models = [name.strip() for name in settings.GEMINI_MODELS.split(",") if name.strip()]
        # De-duplicate while preserving the configured priority order.
        return list(dict.fromkeys(models))

    def screen_for_prompt_injection(self, user_query: str) -> bool:
        """Return True if the query contains suspicious adversarial injection patterns."""
        return llm_safety.screen_for_prompt_injection(user_query)

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
            "4. Output MUST be a valid JSON object with exactly these fields: "
            '{"answer": "...", "scientific_rationale": "...", "approved_actions": ["..."]}. '
            "Do not add other keys. approved_actions must copy strings verbatim "
            "from the APPROVED RECOMMENDATIONS below.\n\n"
            f"VALIDATED TELEMETRY:\n"
            f"- Station: {obs.station.station_name} ({obs.station.city})\n"
            f"- CPCB AQI: {obs.calculated_aqi} ({self._label(obs.aqi_category)})\n"
            f"- Dominant Pollutant: {self._label(obs.dominant_pollutant)}\n"
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

        approved_actions = self._approved_actions(plan)
        try:
            async with asyncio.timeout(settings.LLM_REQUEST_BUDGET_SECONDS):
                if self.gemini_api_key:
                    for model in self._gemini_model_chain():
                        try:
                            result = await self._call_gemini(
                                query, system_prompt, obs, assessment, approved_actions, model
                            )
                        except _LLMPermanentError:
                            logger.warning("Gemini key rejected; stopping model failover chain.")
                            break
                        except Exception as exc:
                            # Log the exception type only: credentials are never included
                            # in upstream URLs or payloads, and must never reach logs.
                            logger.warning(
                                "Gemini model %s failed (%s); trying next model.",
                                model,
                                type(exc).__name__,
                            )
                            continue
                        if result is not None:
                            logger.info("LLM explanation generated with %s.", model)
                            return result
                        logger.warning(
                            "Gemini model %s returned unusable output; trying next model.", model
                        )

                # Groq remains an optional last resort, after the configured free-tier chain.
                if self.groq_api_key:
                    return await self._call_groq(
                        query, system_prompt, obs, assessment, approved_actions
                    )
        except TimeoutError:
            logger.warning("LLM chain exceeded its time budget; invoking deterministic fallback.")
            return None
        except Exception as exc:
            logger.warning(
                "External LLM API call failed (%s); invoking fallback.", type(exc).__name__
            )
            return None

        return None

    @staticmethod
    def _label(value) -> str:
        """Render enums as human-readable labels in generated explanations."""
        return render_label(value)

    @staticmethod
    def _approved_actions(plan: PersonalizedPlan) -> list[str]:
        """Only these deterministic actions may be echoed back by an LLM."""
        seen: set[str] = set()
        actions: list[str] = []
        for item in (
            plan.morning_recommendations
            + plan.afternoon_recommendations
            + plan.evening_recommendations
        ):
            if item.action not in seen:
                seen.add(item.action)
                actions.append(item.action)
        return actions

    @staticmethod
    def _answer_is_grounded(answer: str, validated_aqi: Optional[int]) -> bool:
        """Reject LLM answers that assert an AQI other than the validated value."""
        return llm_safety.answer_is_grounded(answer, validated_aqi)

    @classmethod
    def _build_grounded_explanation(
        cls,
        parsed: dict,
        obs: NormalizedObservation,
        assessment: EnvironmentalAssessment,
        approved_actions: list[str],
    ) -> Optional[ExplanationResponse]:
        answer = parsed.get("answer")
        rationale = parsed.get("scientific_rationale")
        if not isinstance(answer, str) or not answer.strip():
            return None
        if not isinstance(rationale, str) or not rationale.strip():
            return None
        if not cls._answer_is_grounded(answer, obs.calculated_aqi):
            return None
        # Defence in depth: never echo generated control tokens into the UI,
        # even if the upstream model was successfully prompt-injected.
        if any(
            marker in normalize_for_screening(field)
            for field in (answer, rationale)
            for marker in INJECTION_MARKERS
        ):
            logger.warning("Discarding LLM output containing control tokens")
            return None

        raw_actions = parsed.get("approved_actions")
        safe_actions = (
            [
                action.strip()
                for action in raw_actions
                if isinstance(action, str) and action.strip() in approved_actions
            ]
            if isinstance(raw_actions, list)
            else []
        )

        # Baseline fields and actions cannot be tampered with by the LLM.
        return ExplanationResponse(
            answer=answer[:2000],
            referenced_aqi=obs.calculated_aqi,
            dominant_pollutant=obs.dominant_pollutant,
            risk_level=assessment.risk_level,
            approved_actions=safe_actions or approved_actions[:2],
            scientific_rationale=rationale[:1000],
            provider_provenance=obs.provider,
            llm_grounded=True,
        )

    @staticmethod
    def _parse_json_object(text: str) -> Optional[dict]:
        """Parse a JSON object from a model reply, tolerating code fences/prose."""
        return _parse_json_object(text)

    async def _call_groq(
        self,
        query: str,
        system_prompt: str,
        obs: NormalizedObservation,
        assessment: EnvironmentalAssessment,
        approved_actions: list[str],
    ) -> Optional[ExplanationResponse]:
        return await call_groq(self, query, system_prompt, obs, assessment, approved_actions)

    async def _call_gemini(
        self,
        query: str,
        system_prompt: str,
        obs: NormalizedObservation,
        assessment: EnvironmentalAssessment,
        approved_actions: list[str],
        model: str,
    ) -> Optional[ExplanationResponse]:
        return await call_gemini(
            self, query, system_prompt, obs, assessment, approved_actions, model
        )

    def _generate_deterministic_fallback(
        self,
        query: str,
        obs: NormalizedObservation,
        assessment: EnvironmentalAssessment,
        plan: PersonalizedPlan,
        profile: HouseholdProfile,
    ) -> ExplanationResponse:
        return generate_deterministic_fallback(query, obs, assessment, plan, profile, self._label)
