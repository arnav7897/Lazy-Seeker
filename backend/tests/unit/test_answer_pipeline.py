"""
Unit tests for the Answer Pipeline.

All external services (cache, Ollama, Gemini) are mocked so tests
run fully offline and deterministically.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.answer_pipeline import get_answer, AnswerResponse
from app.services.cache_service import CacheResult


# ── Fixtures & Helpers ────────────────────────────────────────────────────────

def _cache_hit(answer_text="Cached answer", score=0.92):
    m = MagicMock()
    m.answer_text = answer_text
    m.question_type = "skills"
    m.id = "cache-123"
    return CacheResult(hit=True, answer=m, score=score)


def _cache_suggestion(answer_text="Suggested answer", score=0.72):
    m = MagicMock()
    m.answer_text = answer_text
    m.question_type = "skills"
    m.question_text = "Original question text"
    m.id = "cache-456"
    return CacheResult(hit=False, suggestion=m, score=score, needs_review=True)


def _cache_miss():
    return CacheResult(hit=False, score=0.1)


def _classification(question_type="skills", needs_personalization=False, optimized_prompt="Optimized Q"):
    from app.services.ollama_service import ClassificationResult
    return ClassificationResult(
        question_type=question_type,
        needs_personalization=needs_personalization,
        optimized_prompt=optimized_prompt,
        key_context=[],
    )


def _stored_entry(answer_text="Gemini answer"):
    m = MagicMock()
    m.id = "cache-new"
    m.answer_text = answer_text
    return m


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestAnswerPipeline:

    async def test_pipeline_returns_cache_hit_without_calling_ollama(self):
        db = AsyncMock()
        with (
            patch("app.services.answer_pipeline.cache_service.find_similar", new=AsyncMock(return_value=_cache_hit())),
            patch("app.services.answer_pipeline.ollama_service.classify_and_optimize", new=AsyncMock()) as mock_ollama,
        ):
            result = await get_answer(user_id="u1", question="Q", db=db)

        assert result.source == "cache"
        assert result.answer == "Cached answer"
        assert result.gemini_calls_made == 0
        assert result.ollama_calls_made == 0
        mock_ollama.assert_not_called()

    async def test_pipeline_calls_ollama_on_cache_miss(self):
        db = AsyncMock()
        with (
            patch("app.services.answer_pipeline.cache_service.find_similar", new=AsyncMock(return_value=_cache_miss())),
            patch("app.services.answer_pipeline.ollama_service.classify_and_optimize",
                  new=AsyncMock(return_value=_classification(needs_personalization=True))) as mock_ollama,
            patch("app.services.answer_pipeline.ollama_service.compress_profile_for_prompt",
                  new=AsyncMock(return_value="Profile summary")),
            patch("app.services.answer_pipeline.gemini_service.generate_answer",
                  new=AsyncMock(return_value="Gemini answer")),
            patch("app.services.answer_pipeline.cache_service.store_answer",
                  new=AsyncMock(return_value=_stored_entry())),
            patch("app.services.answer_pipeline._load_user_context",
                  new=AsyncMock(return_value=({}, []))),
        ):
            result = await get_answer(user_id="u1", question="Q", db=db)

        mock_ollama.assert_called_once()
        assert result.ollama_calls_made >= 1

    async def test_pipeline_skips_gemini_on_suggestion_without_personalization(self):
        db = AsyncMock()
        with (
            patch("app.services.answer_pipeline.cache_service.find_similar",
                  new=AsyncMock(return_value=_cache_suggestion())),
            patch("app.services.answer_pipeline.ollama_service.classify_and_optimize",
                  new=AsyncMock(return_value=_classification(needs_personalization=False))),
            patch("app.services.answer_pipeline.gemini_service.generate_answer",
                  new=AsyncMock()) as mock_gemini,
        ):
            result = await get_answer(user_id="u1", question="Q", db=db)

        assert result.source == "cache_suggestion"
        assert result.needs_review is True
        mock_gemini.assert_not_called()
        assert result.gemini_calls_made == 0

    async def test_pipeline_calls_gemini_when_personalization_needed_despite_suggestion(self):
        db = AsyncMock()
        with (
            patch("app.services.answer_pipeline.cache_service.find_similar",
                  new=AsyncMock(return_value=_cache_suggestion())),
            patch("app.services.answer_pipeline.ollama_service.classify_and_optimize",
                  new=AsyncMock(return_value=_classification(needs_personalization=True))),
            patch("app.services.answer_pipeline.ollama_service.compress_profile_for_prompt",
                  new=AsyncMock(return_value="Compressed")),
            patch("app.services.answer_pipeline.gemini_service.generate_answer",
                  new=AsyncMock(return_value="Personalized answer")) as mock_gemini,
            patch("app.services.answer_pipeline.cache_service.store_answer",
                  new=AsyncMock(return_value=_stored_entry("Personalized answer"))),
            patch("app.services.answer_pipeline._load_user_context",
                  new=AsyncMock(return_value=({}, []))),
        ):
            result = await get_answer(user_id="u1", question="Specific question about Anthropic", db=db)

        mock_gemini.assert_called_once()
        assert result.source == "gemini"
        assert result.gemini_calls_made == 1

    async def test_new_answer_stored_in_cache_after_gemini_call(self):
        db = AsyncMock()
        with (
            patch("app.services.answer_pipeline.cache_service.find_similar",
                  new=AsyncMock(return_value=_cache_miss())),
            patch("app.services.answer_pipeline.ollama_service.classify_and_optimize",
                  new=AsyncMock(return_value=_classification(needs_personalization=True))),
            patch("app.services.answer_pipeline.ollama_service.compress_profile_for_prompt",
                  new=AsyncMock(return_value="Compressed")),
            patch("app.services.answer_pipeline.gemini_service.generate_answer",
                  new=AsyncMock(return_value="Fresh answer")),
            patch("app.services.answer_pipeline.cache_service.store_answer",
                  new=AsyncMock(return_value=_stored_entry("Fresh answer"))) as mock_store,
            patch("app.services.answer_pipeline._load_user_context",
                  new=AsyncMock(return_value=({}, []))),
        ):
            result = await get_answer(user_id="u1", question="New question", db=db)

        mock_store.assert_called_once()
        assert result.cache_id == "cache-new"

    async def test_gemini_call_count_tracked(self):
        db = AsyncMock()
        with (
            patch("app.services.answer_pipeline.cache_service.find_similar",
                  new=AsyncMock(return_value=_cache_miss())),
            patch("app.services.answer_pipeline.ollama_service.classify_and_optimize",
                  new=AsyncMock(return_value=_classification(needs_personalization=True))),
            patch("app.services.answer_pipeline.ollama_service.compress_profile_for_prompt",
                  new=AsyncMock(return_value="Compressed")),
            patch("app.services.answer_pipeline.gemini_service.generate_answer",
                  new=AsyncMock(return_value="Answer")),
            patch("app.services.answer_pipeline.cache_service.store_answer",
                  new=AsyncMock(return_value=_stored_entry())),
            patch("app.services.answer_pipeline._load_user_context",
                  new=AsyncMock(return_value=({}, []))),
        ):
            result = await get_answer(user_id="u1", question="Q", db=db)

        assert result.gemini_calls_made == 1
        assert result.ollama_calls_made == 2   # classify + compress
