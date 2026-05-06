"""
Unit tests for OllamaService.

Since Ollama is a local service that may not be running in CI,
we test:
  1. The classification logic when Ollama returns well-formed JSON
  2. The graceful fallback when Ollama is unreachable
  3. Profile compression output length
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.ollama_service import OllamaService, ClassificationResult


@pytest.fixture
def svc():
    return OllamaService()


class TestClassifyAndOptimize:

    async def test_returns_correct_question_type(self, svc: OllamaService):
        mock_response = json.dumps({
            "question_type": "why_company",
            "key_context": ["mission", "values", "culture"],
            "optimized_prompt": "Why do you want to work here?",
            "needs_personalization": True,
        })
        with patch.object(svc, "_post", new=AsyncMock(return_value=mock_response)):
            result = await svc.classify_and_optimize(
                "Why do you want to work at our company?", "SWE", "Anthropic"
            )
        assert result.question_type == "why_company"
        assert "mission" in result.key_context

    async def test_identifies_needs_personalization_false(self, svc: OllamaService):
        mock_response = json.dumps({
            "question_type": "skills",
            "key_context": ["Python", "ML"],
            "optimized_prompt": "List your top technical skills.",
            "needs_personalization": False,
        })
        with patch.object(svc, "_post", new=AsyncMock(return_value=mock_response)):
            result = await svc.classify_and_optimize("What technical skills do you have?")
        assert result.needs_personalization is False

    async def test_graceful_fallback_when_ollama_unreachable(self, svc: OllamaService):
        with patch.object(svc, "_post", new=AsyncMock(return_value="")):
            result = await svc.classify_and_optimize("Why do you want this role?")
        assert isinstance(result, ClassificationResult)
        assert result.question_type == "general"
        assert result.needs_personalization is True

    async def test_handles_malformed_json_gracefully(self, svc: OllamaService):
        with patch.object(svc, "_post", new=AsyncMock(return_value="not json at all")):
            result = await svc.classify_and_optimize("Any question")
        assert result.question_type == "general"

    async def test_returns_valid_classification_result_type(self, svc: OllamaService):
        mock_response = json.dumps({
            "question_type": "challenge",
            "key_context": ["obstacle"],
            "optimized_prompt": "Describe a challenge.",
            "needs_personalization": False,
        })
        with patch.object(svc, "_post", new=AsyncMock(return_value=mock_response)):
            result = await svc.classify_and_optimize("Tell me about a challenge")
        assert isinstance(result, ClassificationResult)
        assert isinstance(result.key_context, list)
        assert isinstance(result.optimized_prompt, str)


class TestCompressProfile:

    async def test_profile_compression_returns_string(self, svc: OllamaService):
        with patch.object(svc, "_post", new=AsyncMock(return_value="Python expert with 5 years ML experience.")):
            result = await svc.compress_profile_for_prompt(
                profile={"summary": "ML engineer"},
                projects=[{"title": "MyProj", "summary": "Built a model"}],
                question_type="skills",
            )
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_compression_stays_within_reasonable_length(self, svc: OllamaService):
        long_response = "word " * 250   # ~250 words
        with patch.object(svc, "_post", new=AsyncMock(return_value=long_response)):
            result = await svc.compress_profile_for_prompt(
                profile={"summary": "A" * 500}, projects=[], question_type="general"
            )
        # Response is passed through; underlying model enforces the limit
        assert len(result.split()) <= 350   # some tolerance

    async def test_fallback_compress_salary_includes_range(self, svc: OllamaService):
        with patch.object(svc, "_post", new=AsyncMock(return_value="")):
            result = await svc.compress_profile_for_prompt(
                profile={"salary_min": 100000, "salary_max": 140000},
                projects=[],
                question_type="salary",
            )
        assert "100,000" in result or "140,000" in result

    async def test_is_available_returns_bool(self, svc: OllamaService):
        """ping should return a boolean regardless of connection state."""
        result = await svc.is_available()
        assert isinstance(result, bool)
