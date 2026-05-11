"""
Answer Pipeline — The central routing brain.

Every question goes through this exact flow:

  1. Check answer cache (no API calls yet)
     → HIT  : return cached answer immediately
     → MISS : continue

  2. Ollama classifies question type + decides if personalization needed

  3. If suggestion exists AND no personalization needed → return suggestion for review

  4. Ollama compresses profile to relevant context only

  5. Gemini generates answer from compressed profile + optimized prompt

  6. Store new answer in cache for future reuse

Source labels returned to the caller:
  "cache"            — exact/near-exact cache hit, no API calls
  "cache_suggestion" — moderate similarity, user should review
  "gemini"           — freshly generated, stored in cache
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import Profile, Education, Experience, Project, Skill
from app.services.cache_service import cache_service, CacheResult
from app.services.ollama_service import ollama_service, ClassificationResult
from app.services.gemini_service import gemini_service

logger = logging.getLogger(__name__)


@dataclass
class AnswerResponse:
    answer: str
    source: str                      # "cache" | "cache_suggestion" | "gemini"
    question_type: str = "general"
    confidence: float = 1.0
    cache_id: Optional[str] = None   # set when source == "cache"
    needs_review: bool = False
    original_question: Optional[str] = None   # for cache_suggestion source
    gemini_calls_made: int = 0
    ollama_calls_made: int = 0


async def _load_user_context(user_id: str, db: AsyncSession) -> tuple[dict, list[dict]]:
    """Load profile fields and projects for a user as plain dicts."""

    profile_row = await db.execute(
        select(Profile).where(Profile.user_id == user_id)
    )
    profile_obj = profile_row.scalar_one_or_none()
    profile: dict = {}
    if profile_obj:
        profile = {
            c.name: getattr(profile_obj, c.name)
            for c in Profile.__table__.columns
        }

    projects_row = await db.execute(
        select(Project).where(Project.user_id == user_id, Project.do_not_use == False)
    )
    projects: list[dict] = [
        {c.name: getattr(p, c.name) for c in Project.__table__.columns}
        for p in projects_row.scalars().all()
    ]
    return profile, projects


async def get_answer(
    *,
    user_id: str,
    question: str,
    job_title: str = "",
    company: str = "",
    tone: str = "professional",
    max_words: int = 150,
    db: AsyncSession,
) -> AnswerResponse:
    """
    Main entry point. Returns an AnswerResponse with the answer and metadata.
    Counts Gemini/Ollama calls so callers can log the API budget.
    """
    gemini_calls = 0
    ollama_calls = 0

    # ── Step 1: Cache lookup ────────────────────────────────────────────────
    cache_result: CacheResult = await cache_service.find_similar(user_id, question, db)

    if cache_result.hit:
        logger.info("Cache HIT (score=%.3f) — skipping all API calls", cache_result.score)
        return AnswerResponse(
            answer=cache_result.answer.answer_text,
            source="cache",
            question_type=cache_result.answer.question_type or "general",
            confidence=cache_result.score,
            cache_id=cache_result.answer.id,
            gemini_calls_made=0,
            ollama_calls_made=0,
        )

    # ── Step 2: Ollama classification ───────────────────────────────────────
    classification: ClassificationResult = await ollama_service.classify_and_optimize(
        question=question, job_title=job_title, company=company
    )
    ollama_calls += 1
    question_type = classification.question_type
    logger.info("Ollama classified as '%s', needs_personalization=%s",
                question_type, classification.needs_personalization)

    # ── Step 3: Cache suggestion (no personalization needed) ────────────────
    if cache_result.suggestion and not classification.needs_personalization:
        logger.info("Cache SUGGESTION (score=%.3f) — returning for review", cache_result.score)
        return AnswerResponse(
            answer=cache_result.suggestion.answer_text,
            source="cache_suggestion",
            question_type=question_type,
            confidence=cache_result.score,
            cache_id=cache_result.suggestion.id,
            needs_review=True,
            original_question=cache_result.suggestion.question_text,
            gemini_calls_made=0,
            ollama_calls_made=ollama_calls,
        )

    # ── Step 4: Compress profile via Ollama ─────────────────────────────────
    profile, projects = await _load_user_context(user_id, db)
    compressed_profile = await ollama_service.compress_profile_for_prompt(
        profile=profile,
        projects=projects,
        question_type=question_type,
    )
    ollama_calls += 1

    # ── Step 5: Gemini generates the answer ─────────────────────────────────
    optimized_question = classification.optimized_prompt or question
    answer_text = await gemini_service.generate_answer(
        question=optimized_question,
        question_type=question_type,
        compressed_profile=compressed_profile,
        job_title=job_title,
        company=company,
        tone=tone,
        max_words=max_words,
    )
    gemini_calls += 1
    logger.info("Gemini generated answer (%d chars)", len(answer_text))

    # ── Step 6: Store in cache ───────────────────────────────────────────────
    cached = await cache_service.store_answer(
        user_id=user_id,
        question=question,
        answer=answer_text,
        question_type=question_type,
        tone=tone,
        db=db,
    )

    return AnswerResponse(
        answer=answer_text,
        source="gemini",
        question_type=question_type,
        confidence=1.0,
        cache_id=cached.id,
        gemini_calls_made=gemini_calls,
        ollama_calls_made=ollama_calls,
    )
