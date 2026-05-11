"""
Gemini Service — Called ONLY when the answer cache misses.

Responsibilities:
  1. generate_answer()   — Answer a job application question
  2. parse_job_description() — Extract structured data from raw JD text
  3. tailor_resume()     — Match user profile to JD and produce tailored content
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import google.genai as genai
from google.genai import types as genai_types

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Model config ─────────────────────────────────────────────────────────────
_client: genai.Client | None = None   # lazy-init so tests can mock before first use


def _get_model():
    global _client
    if _client is None:
        if not settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY not set. Add it to backend/.env"
            )
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _extract_json(text: str) -> dict | list:
    """Strip markdown fences and parse JSON from Gemini response."""
    # Remove ```json ... ``` or ``` ... ```
    clean = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    return json.loads(clean)


# ── Prompts ───────────────────────────────────────────────────────────────────

ANSWER_PROMPT = """\
You are writing a job application answer on behalf of the user.

User profile summary (relevant parts only):
{compressed_profile}

Question type: {question_type}
Application question: {question}
Job title: {job_title}
Company: {company}

Rules:
- Use ONLY the information in the profile summary. NEVER invent facts, metrics, or dates.
- If a specific metric is not in the profile, omit it.
- Keep the answer under {max_words} words.
- Tone: {tone}
- Return ONLY the answer text. No explanation, no preamble, no quotation marks.
"""

JD_PARSE_PROMPT = """\
Parse this job description and return a JSON object with these exact keys:
{{
  "job_title": string,
  "company": string,
  "seniority": "intern"|"junior"|"mid"|"senior"|"lead",
  "required_skills": [list of strings],
  "preferred_skills": [list of strings],
  "soft_skills": [list of strings],
  "responsibilities": [top 5 as strings],
  "domain": string (e.g. "machine learning", "frontend", "backend"),
  "location": string,
  "remote": boolean,
  "keywords": [top 10 most important keywords],
  "application_questions": [any explicit questions found in the JD]
}}

Return ONLY valid JSON. No explanation.

Job description:
{jd_text}
"""

TAILOR_RESUME_PROMPT = """\
Create a tailored resume in JSON format for this job.

User profile:
{profile_json}

User projects:
{projects_json}

Target job:
{jd_json}

Return a JSON object with these exact keys:
{{
  "summary": "3-sentence tailored professional summary",
  "top_skills": ["8-10 skills most relevant to the JD"],
  "selected_projects": [
    {{
      "title": string,
      "summary": string,
      "tech_stack": [strings],
      "result": string
    }}
  ],
  "tailored_bullets": [
    {{
      "company": string,
      "title": string,
      "bullets": ["rewritten bullet using JD keywords"]
    }}
  ],
  "cover_letter_opening": "one paragraph"
}}

CRITICAL: Use ONLY real information from the profile. Do NOT invent anything.
Return ONLY valid JSON.
"""

MATCH_SCORE_PROMPT = """\
Compare this user profile to the job description and return a JSON object:
{{
  "overall_score": integer 0-100,
  "skill_match": integer 0-100,
  "experience_match": integer 0-100,
  "missing_skills": [skills in JD not in profile],
  "matching_skills": [skills in both],
  "recommendation": "short 1-sentence hiring recommendation"
}}

User profile:
{profile_json}

Job description (parsed):
{jd_json}

Return ONLY valid JSON.
"""


# ── Service ───────────────────────────────────────────────────────────────────

class GeminiService:

    async def generate_answer(
        self,
        question: str,
        question_type: str,
        compressed_profile: str,
        job_title: str = "",
        company: str = "",
        tone: str = "professional",
        max_words: int = 150,
    ) -> str:
        prompt = ANSWER_PROMPT.format(
            compressed_profile=compressed_profile,
            question_type=question_type,
            question=question,
            job_title=job_title or "the role",
            company=company or "the company",
            max_words=max_words,
            tone=tone,
        )
        client = _get_model()
        response = client.models.generate_content(
            model="gemini-1.5-flash", contents=prompt
        )
        return response.text.strip()

    async def parse_job_description(self, jd_text: str) -> dict:
        if not jd_text or len(jd_text.strip()) < 50:
            raise ValueError("Job description text is too short to parse")

        prompt = JD_PARSE_PROMPT.format(jd_text=jd_text[:8000])
        client = _get_model()
        response = client.models.generate_content(
            model="gemini-1.5-flash", contents=prompt
        )
        return _extract_json(response.text)

    async def tailor_resume(
        self,
        profile: dict,
        projects: list[dict],
        parsed_jd: dict,
    ) -> dict:
        prompt = TAILOR_RESUME_PROMPT.format(
            profile_json=json.dumps(profile, default=str)[:3000],
            projects_json=json.dumps(projects, default=str)[:2000],
            jd_json=json.dumps(parsed_jd, default=str)[:2000],
        )
        client = _get_model()
        response = client.models.generate_content(
            model="gemini-1.5-flash", contents=prompt
        )
        return _extract_json(response.text)

    async def compute_match_score(self, profile: dict, parsed_jd: dict) -> dict:
        prompt = MATCH_SCORE_PROMPT.format(
            profile_json=json.dumps(profile, default=str)[:3000],
            jd_json=json.dumps(parsed_jd, default=str)[:2000],
        )
        client = _get_model()
        response = client.models.generate_content(
            model="gemini-1.5-flash", contents=prompt
        )
        return _extract_json(response.text)


# Singleton
gemini_service = GeminiService()
