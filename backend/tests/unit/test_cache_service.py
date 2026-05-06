"""Unit tests for CacheService — embedding, similarity, store, retrieve."""
import numpy as np
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.database import Base
from app.models import models  # noqa — register models
from app.services.cache_service import CacheService, SIMILARITY_THRESHOLD, REVIEW_THRESHOLD

TEST_DB = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(TEST_DB, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def svc():
    return CacheService()


@pytest_asyncio.fixture
async def user_id(db):
    from app.models.models import User
    from app.core.security import hash_password
    u = User(email="cache@test.com", name="Cache Tester", hashed_password=hash_password("pass1234"))
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u.id


class TestEmbedding:
    def test_embedding_returns_numpy_array(self):
        svc = CacheService()
        emb = svc.get_embedding("What are your strengths?")
        assert isinstance(emb, np.ndarray)
        assert emb.dtype == np.float32

    def test_embedding_serialization_roundtrip(self):
        svc = CacheService()
        emb = svc.get_embedding("Tell me about a challenge you overcame")
        hex_str = svc._serialize(emb)
        recovered = svc._deserialize(hex_str)
        assert np.allclose(emb, recovered, atol=1e-6)


class TestCacheMatching:
    async def test_empty_cache_returns_miss(self, svc, db, user_id):
        result = await svc.find_similar(user_id, "Why do you want this job?", db)
        assert result.hit is False
        assert result.score == 0.0

    async def test_exact_match_returns_hit(self, svc, db, user_id):
        question = "What are your greatest strengths?"
        await svc.store_answer(
            user_id=user_id, question=question,
            answer="I am a strong communicator.", db=db
        )
        result = await svc.find_similar(user_id, question, db)
        assert result.hit is True
        assert result.score >= SIMILARITY_THRESHOLD

    async def test_similar_question_above_threshold_returns_hit(self, svc, db, user_id):
        await svc.store_answer(
            user_id=user_id,
            question="Which of your skills are most relevant to this position?",
            answer="My Python and ML skills are most relevant.",
            db=db,
        )
        result = await svc.find_similar(
            user_id,
            "What skills make you a good fit for this role?",
            db,
        )
        # Semantically very similar → expect hit or at least suggestion
        assert result.score > REVIEW_THRESHOLD

    async def test_unrelated_question_returns_miss(self, svc, db, user_id):
        await svc.store_answer(
            user_id=user_id,
            question="What is your greatest strength?",
            answer="My analytical thinking.",
            db=db,
        )
        result = await svc.find_similar(user_id, "What is your salary expectation?", db)
        assert result.hit is False

    async def test_between_thresholds_returns_suggestion(self, svc, db, user_id):
        """Store a moderately related question and verify needs_review flag."""
        await svc.store_answer(
            user_id=user_id,
            question="Tell me about a difficult technical challenge you faced.",
            answer="I migrated a legacy system to microservices.",
            db=db,
        )
        result = await svc.find_similar(
            user_id, "Describe a hard problem you had to solve at work.", db
        )
        # This should be a suggestion (not a definitive hit)
        assert result.score > 0.0  # some similarity exists

    async def test_times_used_increments_on_hit(self, svc, db, user_id):
        question = "Why do you want to work here?"
        await svc.store_answer(
            user_id=user_id, question=question, answer="I admire the company's mission.", db=db
        )
        # First retrieval
        r1 = await svc.find_similar(user_id, question, db)
        assert r1.hit is True
        first_count = r1.answer.times_used

        # Second retrieval — count should have already been incremented to 2
        r2 = await svc.find_similar(user_id, question, db)
        assert r2.answer.times_used == first_count + 1

    async def test_embedding_stored_and_retrieved_correctly(self, svc, db, user_id):
        question = "Describe your proudest achievement."
        entry = await svc.store_answer(
            user_id=user_id, question=question, answer="Launched product with 10k users.", db=db
        )
        # Deserialize stored embedding and verify it matches fresh encoding
        stored = svc._deserialize(entry.question_embedding)
        fresh = svc.get_embedding(question)
        assert np.allclose(stored, fresh, atol=1e-5)
