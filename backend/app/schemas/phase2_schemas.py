"""Phase 2 Pydantic schemas: Job parsing, answer generation, resume tailoring."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ── Job parsing ──────────────────────────────────────────────────────────────
class JDParseRequest(BaseModel):
    url: Optional[str] = None
    raw_text: Optional[str] = None


class JobOut(BaseModel):
    id: str
    user_id: str
    url: Optional[str]
    job_title: Optional[str]
    company: Optional[str]
    seniority: Optional[str]
    domain: Optional[str]
    location: Optional[str]
    remote: bool
    required_skills: list
    preferred_skills: list
    soft_skills: list
    responsibilities: list
    keywords: list
    application_questions: list
    match_score: Optional[int]
    match_details: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Answer generation ────────────────────────────────────────────────────────
class AnswerRequest(BaseModel):
    question: str
    job_id: Optional[str] = None
    job_title: Optional[str] = ""
    company: Optional[str] = ""
    tone: str = "professional"
    max_words: int = 150


class AnswerOut(BaseModel):
    answer: str
    source: str          # "cache" | "cache_suggestion" | "gemini"
    question_type: str
    confidence: float
    cache_id: Optional[str]
    needs_review: bool = False
    original_question: Optional[str] = None
    gemini_calls_made: int
    ollama_calls_made: int


# ── Resume tailoring ─────────────────────────────────────────────────────────
class TailorRequest(BaseModel):
    job_id: str
    tone: str = "professional"


class TailoredResumeOut(BaseModel):
    job_id: str
    summary: Optional[str]
    top_skills: list
    selected_projects: list
    tailored_bullets: list
    cover_letter_opening: Optional[str]
    pdf_path: Optional[str]


# ── Application tracking ─────────────────────────────────────────────────────
class ApplicationOut(BaseModel):
    id: str
    user_id: str
    job_id: Optional[str]
    url: Optional[str]
    status: str
    resume_pdf_path: Optional[str]
    answers: list
    started_at: datetime
    submitted_at: Optional[datetime]
    notes: Optional[str]

    model_config = {"from_attributes": True}


class ApplicationStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None


# ── Match score ───────────────────────────────────────────────────────────────
class MatchScoreOut(BaseModel):
    job_id: str
    overall_score: int
    skill_match: int
    experience_match: int
    missing_skills: list
    matching_skills: list
    recommendation: str
