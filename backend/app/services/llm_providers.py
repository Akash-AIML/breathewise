"""Server-side LLM provider calls and tolerant structured-output parsing."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Optional

import httpx

from app.core.config import settings
from app.schemas.assistant import ExplanationResponse
from app.schemas.observation import NormalizedObservation
from app.schemas.recommendation import EnvironmentalAssessment

if TYPE_CHECKING:
    from app.services.llm_assistant_service import LLMAssistantService

# Preserve the original logger category after the module split.
logger = logging.getLogger("app.services.llm_assistant_service")


class _LLMPermanentError(Exception):
    """Invalid credentials: retrying other models with the same key cannot help."""


def parse_json_object(text: str) -> Optional[dict]:
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


async def call_groq(
    service: LLMAssistantService,
    query: str,
    system_prompt: str,
    obs: NormalizedObservation,
    assessment: EnvironmentalAssessment,
    approved_actions: list[str],
) -> Optional[ExplanationResponse]:
    """One-shot Groq completion, validated through the service's grounding rules."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {service.groq_api_key}",
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
        parsed = service._parse_json_object(content)
        if parsed is None:
            return None
        return service._build_grounded_explanation(parsed, obs, assessment, approved_actions)


async def call_gemini(
    service: LLMAssistantService,
    query: str,
    system_prompt: str,
    obs: NormalizedObservation,
    assessment: EnvironmentalAssessment,
    approved_actions: list[str],
    model: str,
) -> Optional[ExplanationResponse]:
    """One model in the configured free-tier chain. Never logs the API key."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"x-goog-api-key": service.gemini_api_key, "Content-Type": "application/json"}
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
        settings.GEMMA_MODEL_TIMEOUT_SECONDS if is_gemma else settings.GEMINI_MODEL_TIMEOUT_SECONDS
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            body = resp.text.lower() if hasattr(resp, "text") else ""
            if resp.status_code in (401, 403) or (resp.status_code == 400 and "api key" in body):
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
            text
            for part in parts
            if isinstance(part, dict)
            and not part.get("thought")
            and isinstance((text := part.get("text")), str)
        ]
        if not texts:
            return None
        parsed = service._parse_json_object(texts[-1])
        if parsed is None:
            return None
        return service._build_grounded_explanation(parsed, obs, assessment, approved_actions)
