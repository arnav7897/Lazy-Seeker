"""
JD Parser Service — Stores and retrieves parsed job descriptions.
Also computes profile-to-JD match scores.
"""
from __future__ import annotations

import logging
from app.services.gemini_service import gemini_service

logger = logging.getLogger(__name__)


class JDParserService:
    """Thin wrapper around GeminiService for JD-specific operations."""

    async def parse(self, raw_text: str) -> dict:
        """Parse raw JD text into structured JSON via Gemini."""
        return await gemini_service.parse_job_description(raw_text)

    async def compute_match(self, profile: dict, parsed_jd: dict) -> dict:
        """Return a match score comparing the user's profile against the parsed JD."""
        return await gemini_service.compute_match_score(profile, parsed_jd)


jd_parser_service = JDParserService()
