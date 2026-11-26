"""
Unit tests for the LLM Assistant Service: response schema validation and
free-tier Gemini model failover.

Shared observation/profile/service fixtures live in ``tests/unit/conftest.py``.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import AsyncClient, MockTransport, Response

import app.services.llm_assistant_service as llm_service
from app.core.config import settings
from app.core.policy_engine import assess_environmental_risk, generate_personalized_plan
from app.schemas.assistant import ExplanationResponse
from app.services.llm_assistant_service import LLMAssistantService

# ---------------------------------------------------------------------------
# 3. LLM Response Schema Validation
# ---------------------------------------------------------------------------


class TestLLMResponseValidation:
    @pytest.mark.asyncio
    async def test_groq_malformed_json_falls_back(
        self, service: LLMAssistantService, clean_observation, default_profile
    ):
        """When Groq returns malformed JSON, fall back to deterministic engine."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "not valid json {{{"}}]}

        with (
            patch.object(service, "groq_api_key", "fake_key"),
            patch.object(service, "gemini_api_key", None),
            patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        ):
            mock_post.return_value = mock_resp
            resp = await service.generate_explanation(
                "Can I exercise?", clean_observation, default_profile
            )

        assert isinstance(resp, ExplanationResponse)
        assert resp.llm_grounded is False

    @pytest.mark.asyncio
    async def test_groq_http_error_falls_back(
        self, service: LLMAssistantService, clean_observation, default_profile
    ):
        """When Groq returns HTTP 429, fall back to deterministic engine."""
        mock_resp = MagicMock()
        mock_resp.status_code = 429

        with (
            patch.object(service, "groq_api_key", "fake_key"),
            patch.object(service, "gemini_api_key", None),
            patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        ):
            mock_post.return_value = mock_resp
            resp = await service.generate_explanation(
                "Can I exercise?", clean_observation, default_profile
            )

        assert isinstance(resp, ExplanationResponse)
        assert resp.llm_grounded is False

    @pytest.mark.asyncio
    async def test_groq_network_error_falls_back(
        self, service: LLMAssistantService, clean_observation, default_profile
    ):
        """When Groq raises a network exception, fall back gracefully."""
        with (
            patch.object(service, "groq_api_key", "fake_key"),
            patch.object(service, "gemini_api_key", None),
            patch(
                "httpx.AsyncClient.post",
                new_callable=AsyncMock,
                side_effect=httpx.ConnectError("Connection refused"),
            ),
        ):
            resp = await service.generate_explanation(
                "Can I exercise?", clean_observation, default_profile
            )

        assert isinstance(resp, ExplanationResponse)
        assert resp.llm_grounded is False


# ---------------------------------------------------------------------------
# 6. Free-tier Gemini model failover
# ---------------------------------------------------------------------------


VALID_LLM_JSON = (
    '{"answer": "AQI 75 today.", '
    '"scientific_rationale": "Grounded in the validated observation.", '
    '"approved_actions": []}'
)


class TestGeminiModelFailover:
    @staticmethod
    def _install_mock_client(monkeypatch, handler):
        monkeypatch.setattr(
            llm_service.httpx,
            "AsyncClient",
            lambda **kwargs: AsyncClient(
                transport=MockTransport(handler), timeout=kwargs.get("timeout")
            ),
        )

    def test_default_chain_contains_all_requested_models(self):
        assert settings.GEMINI_MODELS.split(",") == [
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite",
            "gemma-4-31b-it",
            "gemma-4-26b-a4b-it",
        ]

    @pytest.mark.asyncio
    async def test_rate_limited_model_falls_back_to_next(
        self, monkeypatch, service, clean_observation, default_profile
    ):
        monkeypatch.setattr(settings, "GEMINI_MODELS", "model-a,model-b")
        monkeypatch.setattr(service, "gemini_api_key", "fake-key")
        monkeypatch.setattr(service, "groq_api_key", None)
        urls = []

        def handler(request):
            urls.append(str(request.url))
            if "model-a" in str(request.url):
                return Response(429, json={"error": {"message": "rate limited"}})
            return Response(
                200,
                json={"candidates": [{"content": {"parts": [{"text": VALID_LLM_JSON}]}}]},
            )

        self._install_mock_client(monkeypatch, handler)
        result = await service.generate_explanation(
            "What is the air quality?", clean_observation, default_profile
        )
        assert result.llm_grounded is True
        assert result.answer == "AQI 75 today."
        assert len(urls) == 2
        assert "model-a:generateContent" in urls[0]
        assert "model-b:generateContent" in urls[1]

    @pytest.mark.asyncio
    async def test_thinking_model_skips_thought_parts(
        self, monkeypatch, service, clean_observation, default_profile
    ):
        monkeypatch.setattr(settings, "GEMINI_MODELS", "gemma-4-31b-it")
        monkeypatch.setattr(service, "gemini_api_key", "fake-key")
        monkeypatch.setattr(service, "groq_api_key", None)

        def handler(request):
            return Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"thought": True, "text": "internal reasoning"},
                                    {"text": VALID_LLM_JSON},
                                ]
                            }
                        }
                    ]
                },
            )

        self._install_mock_client(monkeypatch, handler)
        result = await service.generate_explanation(
            "What is the air quality?", clean_observation, default_profile
        )
        assert result.llm_grounded is True
        assert "internal reasoning" not in result.answer

    @pytest.mark.asyncio
    async def test_all_models_unavailable_uses_deterministic_fallback(
        self, monkeypatch, service, clean_observation, default_profile
    ):
        monkeypatch.setattr(settings, "GEMINI_MODELS", "model-a,model-b")
        monkeypatch.setattr(service, "gemini_api_key", "fake-key")
        monkeypatch.setattr(service, "groq_api_key", None)
        calls = 0

        def handler(request):
            nonlocal calls
            calls += 1
            return Response(503, json={"error": {"message": "high demand"}})

        self._install_mock_client(monkeypatch, handler)
        result = await service.generate_explanation(
            "What is the air quality?", clean_observation, default_profile
        )
        assert result.llm_grounded is False
        assert calls == 2

    @pytest.mark.asyncio
    async def test_invalid_key_stops_chain(
        self, monkeypatch, service, clean_observation, default_profile
    ):
        monkeypatch.setattr(settings, "GEMINI_MODELS", "model-a,model-b")
        monkeypatch.setattr(service, "gemini_api_key", "fake-key")
        monkeypatch.setattr(service, "groq_api_key", None)
        calls = 0

        def handler(request):
            nonlocal calls
            calls += 1
            return Response(400, json={"error": {"message": "API key not valid"}})

        self._install_mock_client(monkeypatch, handler)
        result = await service.generate_explanation(
            "What is the air quality?", clean_observation, default_profile
        )
        assert result.llm_grounded is False
        assert calls == 1

    @pytest.mark.asyncio
    async def test_failover_logs_never_contain_key(
        self, monkeypatch, service, clean_observation, default_profile, caplog
    ):
        secret = "SUPER_SECRET_GEMINI_KEY_123"  # noqa: S105 - fake key for redaction test
        monkeypatch.setattr(settings, "GEMINI_MODELS", "model-a")
        monkeypatch.setattr(service, "gemini_api_key", secret)
        monkeypatch.setattr(service, "groq_api_key", None)
        self._install_mock_client(
            monkeypatch, lambda request: Response(503, json={"error": {"message": "busy"}})
        )
        with caplog.at_level("WARNING"):
            result = await service.generate_explanation(
                "What is the air quality?", clean_observation, default_profile
            )
        assert result.llm_grounded is False
        assert secret not in caplog.text

    @pytest.mark.asyncio
    async def test_system_prompt_specifies_required_json_schema(
        self, monkeypatch, service, clean_observation, default_profile
    ):
        """A successful model reply must be usable by the grounded validator."""
        monkeypatch.setattr(service, "gemini_api_key", "fake-key")
        monkeypatch.setattr(service, "groq_api_key", None)
        captured = {}

        async def capture(  # noqa: PLR0913, PLR0917 - mirrors LLM provider call signature
            query, system_prompt, obs, assessment, actions, model
        ):
            captured["system_prompt"] = system_prompt

        monkeypatch.setattr(service, "_call_gemini", capture)
        assessment = assess_environmental_risk(clean_observation)
        plan = generate_personalized_plan(assessment, default_profile)
        await service._call_server_llm(
            "What is the air quality?", clean_observation, assessment, plan, default_profile
        )
        prompt = captured["system_prompt"]
        assert '"answer"' in prompt
        assert '"scientific_rationale"' in prompt
        assert '"approved_actions"' in prompt
