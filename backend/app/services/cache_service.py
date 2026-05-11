"""
Answer Cache Service — Semantic similarity matching using sentence-transformers.

This is the most important service: it prevents redundant Gemini API calls by
finding semantically similar questions in the cache using cosine similarity.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AnswerCache

logger = logging.getLogger(__name__)

# Loaded once at import — 80MB, runs fully local on CPU
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading sentence-transformers model (first load may take a moment)...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


SIMILARITY_THRESHOLD = 0.82   # above this → cache hit (no API call)
REVIEW_THRESHOLD = 0.65        # between these → show match, ask user to confirm


@dataclass
class CacheResult:
    hit: bool
    answer: AnswerCache | None = None
    suggestion: AnswerCache | None = None
    score: float = 0.0
    needs_review: bool = False


class CacheService:
    """Semantic answer cache backed by SQLite + in-process cosine similarity."""

    def get_embedding(self, text: str) -> np.ndarray:
        """Return a float32 embedding vector for *text*."""
        return _get_model().encode([text.lower().strip()], convert_to_numpy=True)[0]

    def _serialize(self, embedding: np.ndarray) -> str:
        """Serialize a numpy float32 array to a hex string for SQLite storage."""
        return embedding.astype(np.float32).tobytes().hex()

    def _deserialize(self, hex_str: str) -> np.ndarray:
        """Deserialize a hex string back to a float32 numpy array."""
        return np.frombuffer(bytes.fromhex(hex_str), dtype=np.float32)

    async def find_similar(self, user_id: str, question_text: str, db: AsyncSession) -> CacheResult:
        """
        1. Compute embedding for the incoming question.
        2. Compare against all stored embeddings for this user.
        3. Return CacheResult with hit/suggestion/miss info.
        """
        question_embedding = self.get_embedding(question_text)

        result = await db.execute(
            select(AnswerCache).where(AnswerCache.user_id == user_id)
        )
        all_cached = result.scalars().all()

        if not all_cached:
            return CacheResult(hit=False, score=0.0)

        best_score = 0.0
        best_match: AnswerCache | None = None

        for cached in all_cached:
            try:
                stored_vec = self._deserialize(cached.question_embedding)
                score = float(
                    cosine_similarity(
                        question_embedding.reshape(1, -1),
                        stored_vec.reshape(1, -1),
                    )[0][0]
                )
                if score > best_score:
                    best_score = score
                    best_match = cached
            except Exception as exc:
                logger.warning("Skipping corrupt cache entry %s: %s", cached.id, exc)
                continue

        if best_score >= SIMILARITY_THRESHOLD:
            # Increment usage counter
            await db.execute(
                update(AnswerCache)
                .where(AnswerCache.id == best_match.id)
                .values(
                    times_used=best_match.times_used + 1,
                    last_used_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            await db.refresh(best_match)
            return CacheResult(hit=True, answer=best_match, score=best_score)

        elif best_score >= REVIEW_THRESHOLD:
            return CacheResult(
                hit=False,
                suggestion=best_match,
                score=best_score,
                needs_review=True,
            )

        return CacheResult(hit=False, score=best_score)

    async def store_answer(
        self,
        *,
        user_id: str,
        question: str,
        answer: str,
        question_type: str | None = None,
        tone: str = "professional",
        db: AsyncSession,
    ) -> AnswerCache:
        """Store a new Q&A pair in the cache for future reuse."""
        embedding = self.get_embedding(question)
        entry = AnswerCache(
            user_id=user_id,
            question_text=question,
            normalized_question=question.lower().strip(),
            question_embedding=self._serialize(embedding),
            question_type=question_type,
            answer_text=answer,
            tone=tone,
            times_used=1,
            last_used_at=datetime.now(timezone.utc),
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        logger.info("Stored answer in cache: %s (type=%s)", entry.id, question_type)
        return entry

    async def update_answer(
        self,
        cache_id: str,
        user_id: str,
        answer: str,
        db: AsyncSession,
    ) -> AnswerCache | None:
        result = await db.execute(
            select(AnswerCache).where(
                AnswerCache.id == cache_id, AnswerCache.user_id == user_id
            )
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return None
        entry.answer_text = answer
        await db.commit()
        await db.refresh(entry)
        return entry

    async def delete_answer(self, cache_id: str, user_id: str, db: AsyncSession) -> bool:
        result = await db.execute(
            select(AnswerCache).where(
                AnswerCache.id == cache_id, AnswerCache.user_id == user_id
            )
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return False
        await db.delete(entry)
        await db.commit()
        return True

    async def pin_answer(self, cache_id: str, user_id: str, pinned: bool, db: AsyncSession) -> AnswerCache | None:
        result = await db.execute(
            select(AnswerCache).where(
                AnswerCache.id == cache_id, AnswerCache.user_id == user_id
            )
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return None
        entry.is_pinned = pinned
        await db.commit()
        await db.refresh(entry)
        return entry


# Singleton instance
cache_service = CacheService()
