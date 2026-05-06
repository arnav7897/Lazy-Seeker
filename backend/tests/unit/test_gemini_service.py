"""
Unit tests for GeminiService.
All tests mock _get_model() to avoid real API calls.
Uses the new google-genai client interface: client.models.generate_content()
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch


# ── Shared helpers ────────────────────────────────────────────────────────────

def _mock_response(text: str):
    m = MagicMock()
    m.text = text
    return m


def _mock_client(response_text: str):
    """Return a mock genai.Client where .models.generate_content() returns response_text."""
    client = MagicMock()
    client.models.generate_content.return_value = _mock_response(response_text)
    return client


SAMPLE_JD_PARSED = json.dumps({
    "job_title": "Senior ML Engineer",
    "company": "Acme Corp",
    "seniority": "senior",
    "required_skills": ["Python", "PyTorch", "MLOps"],
    "preferred_skills": ["Kubernetes", "Ray"],
    "soft_skills": ["communication", "leadership"],
    "responsibilities": ["Train models", "Deploy to prod", "Code review"],
    "domain": "machine learning",
    "location": "San Francisco, CA",
    "remote": True,
    "keywords": ["ML", "Python", "model", "deployment"],
    "application_questions": ["Why do you want this role?"],
})

SAMPLE_TAILOR_JSON = json.dumps({
    "summary": "Experienced ML engineer with PyTorch and MLOps expertise.",
    "top_skills": ["Python", "PyTorch", "Kubernetes"],
    "selected_projects": [{"title": "P1", "summary": "s", "tech_stack": ["PyTorch"], "result": "r"}],
    "tailored_bullets": [{"company": "OldCo", "title": "MLE", "bullets": ["Trained models"]}],
    "cover_letter_opening": "I am excited to apply...",
})


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestGenerateAnswer:

    async def test_generate_answer_returns_string(self):
        from app.services.gemini_service import GeminiService
        svc = GeminiService()
        with patch("app.services.gemini_service._get_model",
                   return_value=_mock_client("I bring 5 years of Python and ML experience to this role.")):
            result = await svc.generate_answer(
                question="What skills do you bring?",
                question_type="skills",
                compressed_profile="Python expert, 5 years ML.",
                job_title="ML Engineer",
                company="Acme",
            )
        assert isinstance(result, str)
        assert len(result) > 5

    async def test_generate_answer_strips_whitespace(self):
        from app.services.gemini_service import GeminiService
        svc = GeminiService()
        with patch("app.services.gemini_service._get_model",
                   return_value=_mock_client("   My answer here.   ")):
            result = await svc.generate_answer(
                question="q", question_type="general", compressed_profile="p"
            )
        assert result == "My answer here."


class TestParseJobDescription:

    async def test_jd_parse_returns_required_fields(self):
        from app.services.gemini_service import GeminiService
        svc = GeminiService()
        with patch("app.services.gemini_service._get_model",
                   return_value=_mock_client(SAMPLE_JD_PARSED)):
            result = await svc.parse_job_description(
                "Senior ML Engineer at Acme Corp - 5+ years Python, PyTorch required. "
                "We build large scale AI systems. Remote friendly. Join our team."
            )
        required_fields = ["job_title", "company", "required_skills", "keywords", "seniority"]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"

    async def test_jd_parse_returns_list_fields(self):
        from app.services.gemini_service import GeminiService
        svc = GeminiService()
        with patch("app.services.gemini_service._get_model",
                   return_value=_mock_client(SAMPLE_JD_PARSED)):
            result = await svc.parse_job_description(
                "Some job description for a software engineering role with Python, "
                "React, and cloud experience. Must have 3+ years of experience."
            )
        assert isinstance(result["required_skills"], list)
        assert isinstance(result["keywords"], list)

    async def test_jd_parse_handles_markdown_fences(self):
        from app.services.gemini_service import _extract_json
        fenced = f"```json\n{SAMPLE_JD_PARSED}\n```"
        result = _extract_json(fenced)
        assert result["job_title"] == "Senior ML Engineer"

    async def test_short_jd_text_raises_value_error(self):
        from app.services.gemini_service import GeminiService
        svc = GeminiService()
        with pytest.raises(ValueError, match="too short"):
            await svc.parse_job_description("short")

    async def test_jd_parse_remote_field_is_bool(self):
        from app.services.gemini_service import GeminiService
        svc = GeminiService()
        with patch("app.services.gemini_service._get_model",
                   return_value=_mock_client(SAMPLE_JD_PARSED)):
            result = await svc.parse_job_description(
                "Full stack engineer role at TechCo, remote first, Python and React required, "
                "3+ years experience needed for this exciting position."
            )
        assert isinstance(result["remote"], bool)


class TestTailorResume:

    async def test_tailor_resume_returns_valid_structure(self):
        from app.services.gemini_service import GeminiService
        svc = GeminiService()
        with patch("app.services.gemini_service._get_model",
                   return_value=_mock_client(SAMPLE_TAILOR_JSON)):
            result = await svc.tailor_resume(
                profile={"summary": "ML engineer"},
                projects=[{"title": "Proj1", "summary": "Built something", "tech_stack": ["PyTorch"]}],
                parsed_jd={"job_title": "ML Eng", "required_skills": ["PyTorch"]},
            )
        assert "summary" in result
        assert "top_skills" in result
        assert "selected_projects" in result
        assert "tailored_bullets" in result
        assert "cover_letter_opening" in result

    async def test_tailor_resume_top_skills_is_list(self):
        from app.services.gemini_service import GeminiService
        svc = GeminiService()
        with patch("app.services.gemini_service._get_model",
                   return_value=_mock_client(SAMPLE_TAILOR_JSON)):
            result = await svc.tailor_resume(profile={}, projects=[], parsed_jd={})
        assert isinstance(result["top_skills"], list)
