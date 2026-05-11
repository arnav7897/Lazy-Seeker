"""Pydantic v2 schemas for Auth, Profile, Education, Experience, Project, Skill, AnswerCache."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, model_validator


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
class ProfileUpdate(BaseModel):
    phone: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    work_authorization: Optional[str] = None
    requires_sponsorship: Optional[bool] = None
    willing_to_relocate: Optional[bool] = None
    remote_preference: Optional[str] = None
    notice_period: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    summary: Optional[str] = None


class ProfileOut(ProfileUpdate):
    id: str
    user_id: str
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------
class EducationCreate(BaseModel):
    degree: Optional[str] = None
    field: Optional[str] = None
    institution: Optional[str] = None
    graduation_year: Optional[int] = None
    gpa: Optional[float] = None


class EducationOut(EducationCreate):
    id: str
    user_id: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Experience
# ---------------------------------------------------------------------------
class ExperienceCreate(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: bool = False
    bullets: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)


class ExperienceOut(ExperienceCreate):
    id: str
    user_id: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------
class ProjectCreate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    problem: Optional[str] = None
    result: Optional[str] = None
    tech_stack: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    role: Optional[str] = None
    link: Optional[str] = None
    do_not_use: bool = False


class ProjectUpdate(ProjectCreate):
    pass


class ProjectOut(ProjectCreate):
    id: str
    user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Skill
# ---------------------------------------------------------------------------
class SkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    category: Optional[str] = None       # language, framework, tool, soft
    proficiency: Optional[str] = None    # beginner, intermediate, expert


class SkillOut(SkillCreate):
    id: str
    user_id: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Answer Cache
# ---------------------------------------------------------------------------
class AnswerCacheCreate(BaseModel):
    question_text: str
    answer_text: str
    question_type: Optional[str] = None
    tone: str = "professional"


class AnswerCacheUpdate(BaseModel):
    answer_text: str


class AnswerCacheOut(BaseModel):
    id: str
    user_id: str
    question_text: str
    normalized_question: str
    question_type: Optional[str]
    answer_text: str
    tone: Optional[str]
    times_used: int
    last_used_at: datetime
    jobs_used_on: list
    is_pinned: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CacheMatchResponse(BaseModel):
    hit: bool
    score: float
    needs_review: bool = False
    answer: Optional[AnswerCacheOut] = None
    suggestion: Optional[AnswerCacheOut] = None
