"""
BreatheWise — AI Assistant Endpoint (Stage 3: Explainable AI)

POST /api/v1/assistant/chat
  Accepts a user query grounded in real-time air quality telemetry.
  Runs deterministic Stage 1 & 2 policy engines first; LLM is strictly
  restricted to explaining approved outputs in natural language.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.schemas.assistant import ChatQueryRequest, ExplanationResponse
from app.services.air_quality_service import AirQualityService
from app.services.llm_assistant_service import LLMAssistantService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant")

# Module-level singletons (FastAPI reuses across requests)
_air_quality_service = AirQualityService()
_llm_service = LLMAssistantService()


def get_air_quality_service() -> AirQualityService:
    return _air_quality_service


def get_llm_service() -> LLMAssistantService:
    return _llm_service


@router.post(
    "/chat",
    response_model=ExplanationResponse,
    summary="Conversational AI Assistant (Grounded)",
    description=(
        "Accepts a natural-language question about air quality, health, or daily planning. "
        "Responses are strictly grounded in validated real-time sensor telemetry and "
        "deterministic Stage 1/2 policy outputs. The LLM never calculates risk; "
        "it only explains approved recommendations."
    ),
    response_description="Grounded, evidence-based explanation with approved action list.",
)
async def chat(
    request_body: ChatQueryRequest,
    _request: Request,
    aq_service: AirQualityService = Depends(get_air_quality_service),
    llm_service: LLMAssistantService = Depends(get_llm_service),
) -> ExplanationResponse:
    """
    Stage 3 conversational endpoint:
    1. Fetches validated real-time observation for the given coordinates.
    2. Runs deterministic Stages 1 & 2 (risk + personalized plan).
    3. Calls LLM to narrate — never to calculate — approved outputs.
    4. Falls back to deterministic engine if LLM is unavailable.
    """
    try:
        observation = await aq_service.get_air_quality(
            lat=request_body.lat,
            lon=request_body.lon,
        )
    except Exception as exc:
        logger.error("Air quality fetch failed during assistant query: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Real-time air quality data is currently unavailable. "
                "BreatheWise cannot provide grounded recommendations without validated telemetry."
            ),
        ) from exc

    profile = (
        request_body.profile
        or __import__("app.schemas.profile", fromlist=["HouseholdProfile"]).HouseholdProfile()
    )

    response = await llm_service.generate_explanation(
        query=request_body.query,
        observation=observation,
        profile=profile,
    )
    return response
