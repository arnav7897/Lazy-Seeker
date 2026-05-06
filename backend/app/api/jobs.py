"""
Jobs API — JD parsing, profile matching, resume tailoring, PDF export.

Routes:
  POST /jobs/parse                 — parse a raw JD text or URL
  GET  /jobs                       — list all parsed jobs for the user
  GET  /jobs/:id                   — get one parsed job
  GET  /jobs/:id/match             — compute profile-to-JD match score
  POST /jobs/:id/tailor-resume     — tailor resume + export PDF
  POST /jobs/:id/answer            — answer a specific question for this job
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, Profile, Education, Experience, Project
from app.models.phase2_models import Job
from app.schemas.phase2_schemas import (
    JDParseRequest, JobOut,
    TailorRequest, TailoredResumeOut,
    AnswerRequest, AnswerOut,
    MatchScoreOut,
)
from app.services.jd_parser import jd_parser_service
from app.services.resume_tailor import resume_tailor_service
from app.services.answer_pipeline import get_answer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def _load_profile_dict(user_id: str, db: AsyncSession) -> dict:
    r = await db.execute(select(Profile).where(Profile.user_id == user_id))
    p = r.scalar_one_or_none()
    if not p:
        return {}
    return {c.name: getattr(p, c.name) for c in Profile.__table__.columns}


async def _load_projects(user_id: str, db: AsyncSession) -> list[dict]:
    r = await db.execute(
        select(Project).where(Project.user_id == user_id, Project.do_not_use == False)
    )
    return [{c.name: getattr(p, c.name) for c in Project.__table__.columns} for p in r.scalars().all()]


async def _load_education(user_id: str, db: AsyncSession) -> list[dict]:
    r = await db.execute(select(Education).where(Education.user_id == user_id))
    return [{c.name: getattr(e, c.name) for c in Education.__table__.columns} for e in r.scalars().all()]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/parse", response_model=JobOut, status_code=201)
async def parse_job(
    body: JDParseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Parse a raw JD text (or URL placeholder) and store the structured result."""
    if not body.raw_text and not body.url:
        raise HTTPException(status_code=422, detail="Provide raw_text or url")

    jd_text = body.raw_text or f"Job posting at: {body.url}"
    parsed = await jd_parser_service.parse(jd_text)

    job = Job(
        user_id=current_user.id,
        url=body.url,
        raw_text=body.raw_text,
        job_title=parsed.get("job_title"),
        company=parsed.get("company"),
        seniority=parsed.get("seniority"),
        domain=parsed.get("domain"),
        location=parsed.get("location"),
        remote=parsed.get("remote", False),
        required_skills=parsed.get("required_skills", []),
        preferred_skills=parsed.get("preferred_skills", []),
        soft_skills=parsed.get("soft_skills", []),
        responsibilities=parsed.get("responsibilities", []),
        keywords=parsed.get("keywords", []),
        application_questions=parsed.get("application_questions", []),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("", response_model=list[JobOut])
async def list_jobs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Job).where(Job.user_id == current_user.id).order_by(Job.created_at.desc())
    )
    return r.scalars().all()


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = r.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/match", response_model=MatchScoreOut)
async def get_match_score(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = r.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    profile = await _load_profile_dict(current_user.id, db)
    jd_dict = {
        "job_title": job.job_title, "required_skills": job.required_skills,
        "preferred_skills": job.preferred_skills, "responsibilities": job.responsibilities,
        "domain": job.domain, "keywords": job.keywords,
    }

    scores = await jd_parser_service.compute_match(profile, jd_dict)

    # Persist match score on the job row
    job.match_score = scores.get("overall_score")
    job.match_details = scores
    await db.commit()

    return MatchScoreOut(job_id=job_id, **scores)


@router.post("/{job_id}/tailor-resume", response_model=TailoredResumeOut)
async def tailor_resume(
    job_id: str,
    body: TailorRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = r.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    profile = await _load_profile_dict(current_user.id, db)
    # Attach user name + email from User model for resume header
    profile["name"] = current_user.name
    profile["email"] = current_user.email

    projects = await _load_projects(current_user.id, db)
    education = await _load_education(current_user.id, db)
    jd_dict = {
        "job_title": job.job_title, "company": job.company,
        "required_skills": job.required_skills, "preferred_skills": job.preferred_skills,
        "responsibilities": job.responsibilities, "domain": job.domain,
        "keywords": job.keywords,
    }

    result = await resume_tailor_service.tailor_and_export(
        profile=profile,
        projects=projects,
        education=education,
        parsed_jd=jd_dict,
        user_id=current_user.id,
        job_id=job_id,
    )

    return TailoredResumeOut(
        job_id=job_id,
        summary=result.get("summary"),
        top_skills=result.get("top_skills", []),
        selected_projects=result.get("selected_projects", []),
        tailored_bullets=result.get("tailored_bullets", []),
        cover_letter_opening=result.get("cover_letter_opening"),
        pdf_path=result.get("pdf_path"),
    )


@router.post("/{job_id}/answer", response_model=AnswerOut)
async def answer_question(
    job_id: str,
    body: AnswerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run the full answer pipeline for a specific job."""
    # Resolve job context if not provided
    job_title = body.job_title
    company = body.company
    if job_id and (not job_title or not company):
        r = await db.execute(
            select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
        )
        job = r.scalar_one_or_none()
        if job:
            job_title = job_title or job.job_title or ""
            company = company or job.company or ""

    result = await get_answer(
        user_id=current_user.id,
        question=body.question,
        job_title=job_title,
        company=company,
        tone=body.tone,
        max_words=body.max_words,
        db=db,
    )
    return AnswerOut(
        answer=result.answer,
        source=result.source,
        question_type=result.question_type,
        confidence=result.confidence,
        cache_id=result.cache_id,
        needs_review=result.needs_review,
        original_question=result.original_question,
        gemini_calls_made=result.gemini_calls_made,
        ollama_calls_made=result.ollama_calls_made,
    )


@router.post("/answer", response_model=AnswerOut, tags=["jobs"])
async def answer_question_generic(
    body: AnswerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Answer pipeline without a specific job (uses profile only)."""
    result = await get_answer(
        user_id=current_user.id,
        question=body.question,
        job_title=body.job_title or "",
        company=body.company or "",
        tone=body.tone,
        max_words=body.max_words,
        db=db,
    )
    return AnswerOut(
        answer=result.answer,
        source=result.source,
        question_type=result.question_type,
        confidence=result.confidence,
        cache_id=result.cache_id,
        needs_review=result.needs_review,
        original_question=result.original_question,
        gemini_calls_made=result.gemini_calls_made,
        ollama_calls_made=result.ollama_calls_made,
    )
