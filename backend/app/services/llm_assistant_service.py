import asyncio
import json
import logging
import re
import unicodedata
from typing import Optional

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


class _LLMPermanentError(Exception):
    """Invalid credentials: retrying other models with the same key cannot help."""


# Patterns indicating potential adversarial prompt injection or role hijacking.
# Matching happens on a heavily normalized string, not the raw user input.
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|any\s+)?(previous|prior|above|earlier)\s+(instructions|rules|prompts|directives)",
    r"disregard\s+(all\s+|any\s+)?(previous|prior|above|earlier)\s+(instructions|rules|prompts|directives)",
    r"act\s+as\s+(an\s+|a\s+)?(unrestricted|jailbroken|developer|dan|evil|uncensored)",
    r"override\s+(the\s+)?(risk|aqi|system|safety|policy|rules)",
    r"forget\s+(all\s+|any\s+)?(previous|prior|above|earlier)\s+(rules|instructions)",
    r"you\s+are\s+now\s+(an\s+|a\s+)?(unrestricted|jailbroken|developer|dan)",
    r"system\s*:\s*you\s+(must|are|will|shall)",
    r"reveal\s+(your|the)\s+(system\s+)?prompt",
    r"print\s+(your|the)\s+(system\s+)?prompt",
    r"pretend\s+(to\s+be|you\s+are)\s+(an?\s+)?(system|developer|admin)",
    r"bypass\s+(the\s+)?(safety|security|validation|guardrails)",
]

# Structural control tokens used by common chat templates. These are never
# legitimate in a user question about air quality.
INJECTION_MARKERS = (
    "<|im_start|>",
    "<|im_end|>",
    "<|system|>",
    "<|assistant|>",
    "[inst]",
    "[/inst]",
    "<<sys>>",
    "<</sys>>",
    "### system",
    "### assistant",
    "[system]",
    "role:system",
    '"role":"system"',
)

# Common homoglyphs that could be used to evade a literal keyword check.
HOMOGLYPHS = str.maketrans(
    {
        "а": "a",
        "е": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "х": "x",
        "у": "y",
        "і": "i",
        "ј": "j",
        "ѕ": "s",
        "һ": "h",
        "ԁ": "d",
        "ɡ": "g",
        "ń": "n",
        "ⅰ": "i",
        "ⅼ": "l",
        "０": "0",
        "１": "1",
    }
)


def normalize_for_screening(text: str) -> str:
    """Canonicalize user text so spacing, unicode and homoglyph tricks cannot evade matching."""
    text = unicodedata.normalize("NFKC", text)
    # Replace zero-width/control characters with a space rather than deleting
    # them, so "ignore\u200ball" cannot become the unmatched token "ignoreall".
    text = "".join(
        char if unicodedata.category(char) not in {"Cf", "Cc"} or char in {" ", "\n", "\t"} else " "
        for char in text
    )
    text = text.translate(HOMOGLYPHS)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


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
        """
        Returns True if the query contains suspicious adversarial injection patterns.

        This is a defence-in-depth signal, not the primary guarantee. The user
        query is always sent as *user-role data*, and every LLM field that must
        remain trustworthy (AQI, risk, actions, provenance) is overwritten with
        validated values in ``_build_grounded_explanation``.
        """
        normalized = normalize_for_screening(user_query)
        if any(marker in normalized for marker in INJECTION_MARKERS):
            logger.warning("Prompt injection control token detected in user query")
            return True
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, normalized):
                logger.warning("Prompt injection pattern detected in user query")
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
        if value is None:
            return "unavailable"
        return str(getattr(value, "value", value))

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
        asserted = [
            int(value) for value in re.findall(r"\bAQI\b[^0-9]{0,16}(\d{1,3})", answer, re.I)
        ]
        if validated_aqi is None:
            return not asserted
        return all(value == validated_aqi for value in asserted)

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
        if not isinstance(text, str) or not text.strip():
            return None
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        parsed: object = None
        try:
            parsed = json.loads(cleaned)
        except (ValueError, TypeError):
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start == -1 or end <= start:
                return None
            try:
                parsed = json.loads(cleaned[start : end + 1])
            except (ValueError, TypeError):
                return None
        return parsed if isinstance(parsed, dict) else None

    async def _call_groq(
        self,
        query: str,
        system_prompt: str,
        obs: NormalizedObservation,
        assessment: EnvironmentalAssessment,
        approved_actions: list[str],
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
            parsed = self._parse_json_object(content)
            if parsed is None:
                return None
            return self._build_grounded_explanation(parsed, obs, assessment, approved_actions)

    async def _call_gemini(
        self,
        query: str,
        system_prompt: str,
        obs: NormalizedObservation,
        assessment: EnvironmentalAssessment,
        approved_actions: list[str],
        model: str,
    ) -> Optional[ExplanationResponse]:
        """One model in the configured free-tier chain. Never logs the API key."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {"x-goog-api-key": self.gemini_api_key, "Content-Type": "application/json"}
        # Gemma 4 models emit a long `thought` part before the JSON answer, so
        # they need a larger output budget and a longer read timeout.
        is_gemma = model.startswith("gemma-")
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": query}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "maxOutputTokens": 2048 if is_gemma else 800,
            },
        }
        timeout = (
            settings.GEMMA_MODEL_TIMEOUT_SECONDS
            if is_gemma
            else settings.GEMINI_MODEL_TIMEOUT_SECONDS
        )

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                body = resp.text.lower() if hasattr(resp, "text") else ""
                if resp.status_code in (401, 403) or (
                    resp.status_code == 400 and "api key" in body
                ):
                    raise _LLMPermanentError("Gemini key rejected")
                logger.warning(
                    "Gemini model %s returned HTTP %s; trying next model.", model, resp.status_code
                )
                return None

            data = resp.json()
            candidates = data.get("candidates") or []
            if not candidates:
                return None
            parts = (candidates[0].get("content") or {}).get("parts") or []
            # Thinking models (Gemma 4, Gemini 3) put reasoning in parts flagged
            # `thought: true`. Only the final non-thought text part is an answer.
            texts = [
                part.get("text")
                for part in parts
                if isinstance(part, dict)
                and not part.get("thought")
                and isinstance(part.get("text"), str)
            ]
            if not texts:
                return None
            parsed = self._parse_json_object(texts[-1])
            if parsed is None:
                return None
            return self._build_grounded_explanation(parsed, obs, assessment, approved_actions)

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
        aqi = obs.calculated_aqi
        risk = assessment.risk_level

        if aqi is None:
            return ExplanationResponse(
                answer=(
                    f"Validated AQI is unavailable at {obs.station.station_name}. I cannot confirm whether "
                    "outdoor activity is safe right now. Keep strenuous outdoor plans on hold, use indoor "
                    "alternatives, and check validated CPCB telemetry or official advisories before proceeding."
                ),
                referenced_aqi=None,
                dominant_pollutant=obs.dominant_pollutant,
                risk_level=risk,
                approved_actions=[item.action for item in plan.morning_recommendations[:2]],
                scientific_rationale=(
                    "CPCB AQI requires at least three valid pollutant sub-indices, one of them particulate."
                ),
                provider_provenance=obs.provider,
                llm_grounded=False,
            )

        # Category 1: Exercise / Outdoor Workouts
        if any(w in q for w in ("exercise", "workout", "jog", "run", "walk", "sports", "gym")):
            if aqi > 200:
                answer = (
                    f"It is NOT safe to exercise outdoors right now. The current AQI at {obs.station.station_name} "
                    f"is {aqi} ({self._label(obs.aqi_category)}), with {self._label(obs.dominant_pollutant)} as the dominant pollutant. "
                    "Vigorous outdoor exercise increases your minute ventilation rate by up to 500%, pulling fine combustion "
                    "soot deep into your alveolar lung tissue. Please shift workouts to an indoor enclosed space."
                )
                rationale = "Cold morning inversion traps PM2.5 in the breathing zone. Exercise escalates inhaled particulate dose."
                actions = [
                    "Cancel outdoor running, jogging, and cycling.",
                    "Exercise indoors with windows closed and air purifier active.",
                ]
            else:
                answer = (
                    f"Outdoor exercise is acceptable under current conditions (AQI: {aqi}, Category: {self._label(obs.aqi_category)}). "
                    "However, schedule physical activities for mid-afternoon when atmospheric dispersion is greatest."
                )
                rationale = "Particulate levels are within acceptable thresholds for moderate physical activity."
                actions = ["Keep outdoor workouts to light or moderate intensity."]

        # Category 2: Children / Recess / School
        elif any(
            w in q
            for w in (
                "child",
                "children",
                "kid",
                "kids",
                "baby",
                "infant",
                "school",
                "recess",
                "play",
            )
        ):
            if aqi > 150:
                answer = (
                    f"Children should avoid outdoor physical play at this time. With an ambient AQI of {aqi} ({self._label(obs.aqi_category)}), "
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
                    f"Current air quality (AQI: {aqi}, Category: {self._label(obs.aqi_category)}) is within safe limits for children's outdoor play "
                    "and school sports."
                )
                rationale = "Criteria pollutants do not exceed national pediatric safety standards."
                actions = ["Permit standard outdoor school activities."]

        # Category 3: Indoor Air & Houseplants
        elif any(
            w in q
            for w in ("plant", "houseplant", "snake plant", "indoor", "purifier", "filter", "cadr")
        ):
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
        elif any(
            w in q
            for w in ("commute", "travel", "metro", "bus", "car", "bike", "cycle", "mask", "n95")
        ):
            if aqi > 100:
                answer = (
                    f"For commuting in current air ({aqi} AQI, {self._label(obs.dominant_pollutant)}), the electric metro is your safest and cleanest option. "
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
                answer = f"Current ambient road air is satisfactory (AQI: {aqi}). Public transit, metro, and active cycling are all acceptable."
                rationale = "Ambient criteria pollutants are within standard limits."
                actions = ["Standard commute routines without specialized respirators."]

        # Category 5: General / Why was this recommended
        else:
            answer = (
                f"Based on real-time sensor measurements from {obs.station.station_name}, your current AQI is {aqi} "
                f"({self._label(obs.aqi_category)}), with {self._label(obs.dominant_pollutant)} as the dominant criteria pollutant. "
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
