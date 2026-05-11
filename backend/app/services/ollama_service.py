"""
Ollama Service — Local prompt optimizer and question classifier.

Ollama's job is NOT to answer application questions.
Its three responsibilities:
  1. Classify the question type (why_company, skills, challenge, etc.)
  2. Compress the user profile down to only the relevant facts for that question type
  3. Rewrite the question into a clean, token-efficient prompt for Gemini
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

CLASSIFIER_PROMPT = """\
You are a job application question classifier and prompt optimizer.

Given a job application question, return a JSON object with these exact keys:
- "question_type": one of [why_company, why_role, skills, challenge, achievement,
                            salary, availability, sponsorship, work_auth, strength,
                            weakness, project, culture_fit, general]
- "key_context": list of 3-5 keywords from the question that matter most
- "optimized_prompt": a shorter, cleaner rewrite of the question (max 25 words)
- "needs_personalization": true if the answer MUST reference this specific company/role,
                            false if a generic answer works

Return ONLY valid JSON. No explanation, no markdown fences.

Question: {question}
Job role: {job_title}
Company: {company}
"""

COMPRESS_PROFILE_PROMPT = """\
You are a resume data extractor.

Given a user profile (JSON) and a list of projects (JSON), extract ONLY the parts
relevant to answering a '{question_type}' type job application question.

Rules:
- Return a plain-text summary under 200 words
- Use only facts from the input, never invent anything
- Be concise: only include what matters for this question type

User profile:
{profile_json}

Projects:
{projects_json}
"""


@dataclass
class ClassificationResult:
    question_type: str = "general"
    key_context: list[str] = field(default_factory=list)
    optimized_prompt: str = ""
    needs_personalization: bool = True
    raw: dict = field(default_factory=dict)


class OllamaService:
    """Wraps the local Ollama HTTP API."""

    def __init__(self):
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model
        self._generate_url = f"{self.base_url}/api/generate"

    async def _post(self, prompt: str, *, use_json_format: bool = False, timeout: float = 45.0) -> str:
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if use_json_format:
            payload["format"] = "json"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self._generate_url, json=payload, timeout=timeout)
                resp.raise_for_status()
                return resp.json().get("response", "")
        except httpx.ConnectError:
            logger.warning("Ollama not reachable at %s — falling back to passthrough", self.base_url)
            return ""
        except Exception as exc:
            logger.error("Ollama error: %s", exc)
            return ""

    async def classify_and_optimize(
        self,
        question: str,
        job_title: str = "",
        company: str = "",
    ) -> ClassificationResult:
        """
        Classify question type and produce an optimized prompt.
        Falls back to safe defaults if Ollama is unreachable.
        """
        prompt = CLASSIFIER_PROMPT.format(
            question=question,
            job_title=job_title or "unknown",
            company=company or "unknown",
        )
        raw_response = await self._post(prompt, use_json_format=True)

        if not raw_response:
            return ClassificationResult(
                question_type="general",
                optimized_prompt=question,
                needs_personalization=True,
            )

        try:
            data = json.loads(raw_response)
            return ClassificationResult(
                question_type=data.get("question_type", "general"),
                key_context=data.get("key_context", []),
                optimized_prompt=data.get("optimized_prompt", question),
                needs_personalization=data.get("needs_personalization", True),
                raw=data,
            )
        except json.JSONDecodeError:
            logger.warning("Ollama returned non-JSON: %s", raw_response[:200])
            return ClassificationResult(
                question_type="general",
                optimized_prompt=question,
                needs_personalization=True,
            )

    async def compress_profile_for_prompt(
        self,
        profile: dict,
        projects: list[dict],
        question_type: str,
    ) -> str:
        """
        Ask Ollama to distil the user's full profile into a ≤200 word
        relevant summary for the given question_type.
        Falls back to a minimal JSON snippet if Ollama is unreachable.
        """
        prompt = COMPRESS_PROFILE_PROMPT.format(
            question_type=question_type,
            profile_json=json.dumps(profile, default=str)[:3000],
            projects_json=json.dumps(projects, default=str)[:2000],
        )
        response = await self._post(prompt, timeout=45.0)

        if not response:
            # Fallback: build a simple summary from profile fields
            return self._fallback_compress(profile, projects, question_type)

        return response.strip()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_compress(profile: dict, projects: list[dict], question_type: str) -> str:
        """Minimal profile summary when Ollama is offline."""
        parts: list[str] = []
        if profile.get("summary"):
            parts.append(f"Summary: {profile['summary']}")
        if profile.get("salary_min") and question_type == "salary":
            parts.append(f"Salary range: ${profile['salary_min']:,}–${profile['salary_max']:,}")
        if profile.get("notice_period") and question_type == "availability":
            parts.append(f"Notice period: {profile['notice_period']}")
        if profile.get("work_authorization") and question_type in ("work_auth", "sponsorship"):
            parts.append(f"Work auth: {profile['work_authorization']}")
            parts.append(f"Requires sponsorship: {profile.get('requires_sponsorship', False)}")
        if projects and question_type == "project":
            p = projects[0]
            parts.append(f"Key project: {p.get('title')} — {p.get('summary', '')}")
        return " | ".join(parts) if parts else "Profile data available."

    async def is_available(self) -> bool:
        """Quick ping to check if Ollama is running."""
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{self.base_url}/api/tags", timeout=3.0)
                return r.status_code == 200
        except Exception:
            return False


# Singleton
ollama_service = OllamaService()
