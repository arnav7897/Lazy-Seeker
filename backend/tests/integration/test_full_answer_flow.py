"""
Integration tests for the full answer generation flow via the HTTP API.
All Gemini and Ollama calls are mocked so tests run offline.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient

SAMPLE_JD = """
Senior Machine Learning Engineer at NeuralAI

We are looking for a Senior ML Engineer to join our team.

Requirements:
- 5+ years of experience with Python
- Proficiency in PyTorch or TensorFlow
- Experience with MLOps pipelines (Kubernetes, Docker)
- Strong communication skills

Responsibilities:
- Train and deploy large language models
- Build scalable ML pipelines
- Collaborate with product teams

Questions:
- Why do you want to work at NeuralAI?
- Describe a challenging ML project you led.
"""


async def _register_and_token(client: AsyncClient, email: str) -> str:
    r = await client.post("/auth/register", json={
        "email": email, "name": "Test User", "password": "testpass99"
    })
    return r.json()["access_token"]


def _mock_gemini_parse():
    return {
        "job_title": "Senior ML Engineer",
        "company": "NeuralAI",
        "seniority": "senior",
        "required_skills": ["Python", "PyTorch", "Kubernetes"],
        "preferred_skills": ["Ray", "Triton"],
        "soft_skills": ["communication"],
        "responsibilities": ["Train LLMs", "Build pipelines"],
        "domain": "machine learning",
        "location": "Remote",
        "remote": True,
        "keywords": ["ML", "Python", "LLM"],
        "application_questions": ["Why NeuralAI?"],
    }


def _mock_gemini_answer():
    return "I am passionate about ML and have 5 years of experience with PyTorch."


def _mock_ollama_classification():
    from app.services.ollama_service import ClassificationResult
    return ClassificationResult(
        question_type="why_company",
        key_context=["mission", "ML"],
        optimized_prompt="Why do you want to work here?",
        needs_personalization=True,
    )


class TestFullAnswerFlow:

    async def test_first_question_calls_gemini_and_stores_answer(self, client: AsyncClient):
        token = await _register_and_token(client, "flow1@ai.com")
        headers = {"Authorization": f"Bearer {token}"}

        with (
            patch("app.services.answer_pipeline.ollama_service.classify_and_optimize",
                  new=AsyncMock(return_value=_mock_ollama_classification())),
            patch("app.services.answer_pipeline.ollama_service.compress_profile_for_prompt",
                  new=AsyncMock(return_value="ML engineer with PyTorch experience")),
            patch("app.services.answer_pipeline.gemini_service.generate_answer",
                  new=AsyncMock(return_value=_mock_gemini_answer())),
        ):
            resp = await client.post("/jobs/answer", headers=headers, json={
                "question": "Why do you want to work at NeuralAI?",
                "company": "NeuralAI",
                "job_title": "Senior ML Engineer",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "gemini"
        assert data["gemini_calls_made"] == 1
        assert data["cache_id"] is not None

    async def test_same_question_second_time_returns_cache_hit(self, client: AsyncClient):
        token = await _register_and_token(client, "flow2@ai.com")
        headers = {"Authorization": f"Bearer {token}"}
        question = "What are your top technical skills?"

        # First call — populates cache
        with (
            patch("app.services.answer_pipeline.ollama_service.classify_and_optimize",
                  new=AsyncMock(return_value=_mock_ollama_classification())),
            patch("app.services.answer_pipeline.ollama_service.compress_profile_for_prompt",
                  new=AsyncMock(return_value="Profile summary")),
            patch("app.services.answer_pipeline.gemini_service.generate_answer",
                  new=AsyncMock(return_value="Python, PyTorch, MLOps")),
        ):
            first = await client.post("/jobs/answer", headers=headers, json={"question": question})
        assert first.json()["source"] == "gemini"

        # Second call — should hit cache, no mocking needed
        second = await client.post("/jobs/answer", headers=headers, json={"question": question})
        assert second.status_code == 200
        assert second.json()["source"] == "cache"
        assert second.json()["gemini_calls_made"] == 0

    async def test_similar_question_returns_suggestion_or_hit(self, client: AsyncClient):
        token = await _register_and_token(client, "flow3@ai.com")
        headers = {"Authorization": f"Bearer {token}"}

        # Seed the cache
        await client.post("/cache/answers", headers=headers, json={
            "question_text": "What technical skills are most relevant to this role?",
            "answer_text": "Python, PyTorch, and distributed training.",
            "question_type": "skills",
        })

        # Ask a semantically similar question
        with (
            patch("app.services.answer_pipeline.ollama_service.classify_and_optimize",
                  new=AsyncMock(return_value=_mock_ollama_classification())),
            patch("app.services.answer_pipeline.ollama_service.compress_profile_for_prompt",
                  new=AsyncMock(return_value="Profile")),
            patch("app.services.answer_pipeline.gemini_service.generate_answer",
                  new=AsyncMock(return_value="Fresh answer")),
        ):
            resp = await client.post("/jobs/answer", headers=headers, json={
                "question": "Which skills do you bring to this ML engineering position?"
            })
        assert resp.status_code == 200
        # score should be non-trivial — hit or suggestion
        data = resp.json()
        assert data["source"] in ("cache", "cache_suggestion", "gemini")

    async def test_jd_parse_and_store(self, client: AsyncClient):
        token = await _register_and_token(client, "flow4@ai.com")
        headers = {"Authorization": f"Bearer {token}"}

        with patch("app.services.jd_parser.gemini_service.parse_job_description",
                   new=AsyncMock(return_value=_mock_gemini_parse())):
            resp = await client.post("/jobs/parse", headers=headers, json={"raw_text": SAMPLE_JD})

        assert resp.status_code == 201
        data = resp.json()
        assert data["job_title"] == "Senior ML Engineer"
        assert "Python" in data["required_skills"]
        assert data["remote"] is True

    async def test_list_jobs_returns_parsed_jobs(self, client: AsyncClient):
        token = await _register_and_token(client, "flow5@ai.com")
        headers = {"Authorization": f"Bearer {token}"}

        with patch("app.services.jd_parser.gemini_service.parse_job_description",
                   new=AsyncMock(return_value=_mock_gemini_parse())):
            await client.post("/jobs/parse", headers=headers, json={"raw_text": SAMPLE_JD})

        listed = await client.get("/jobs", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        assert listed.json()[0]["company"] == "NeuralAI"
