"""Additional models for Phase 2: Job and Application."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Job(Base):
    """Parsed job description stored per user."""
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    url: Mapped[str | None] = mapped_column(String)
    raw_text: Mapped[str | None] = mapped_column(Text)
    job_title: Mapped[str | None] = mapped_column(String)
    company: Mapped[str | None] = mapped_column(String)
    seniority: Mapped[str | None] = mapped_column(String)
    domain: Mapped[str | None] = mapped_column(String)
    location: Mapped[str | None] = mapped_column(String)
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    preferred_skills: Mapped[list] = mapped_column(JSON, default=list)
    soft_skills: Mapped[list] = mapped_column(JSON, default=list)
    responsibilities: Mapped[list] = mapped_column(JSON, default=list)
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    application_questions: Mapped[list] = mapped_column(JSON, default=list)
    match_score: Mapped[int | None] = mapped_column(Integer)   # 0-100
    match_details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    applications: Mapped[list["Application"]] = relationship("Application", back_populates="job", cascade="all, delete-orphan")


class Application(Base):
    """Tracks each job application attempt."""
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    job_id: Mapped[str | None] = mapped_column(String, ForeignKey("jobs.id"))
    url: Mapped[str | None] = mapped_column(String)
    # status: saved | drafted | submitted | interview | rejected | offer | withdrawn
    status: Mapped[str] = mapped_column(String, default="drafted")
    resume_pdf_path: Mapped[str | None] = mapped_column(String)
    tailored_resume: Mapped[dict | None] = mapped_column(JSON)
    answers: Mapped[list] = mapped_column(JSON, default=list)   # [{question, answer}]
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    job: Mapped["Job | None"] = relationship("Job", back_populates="applications")
