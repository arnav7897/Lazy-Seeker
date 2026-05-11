import uuid
from datetime import datetime, date, timezone
from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Date,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


def gen_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    profile: Mapped["Profile"] = relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    education: Mapped[list["Education"]] = relationship("Education", back_populates="user", cascade="all, delete-orphan")
    experience: Mapped[list["Experience"]] = relationship("Experience", back_populates="user", cascade="all, delete-orphan")
    projects: Mapped[list["Project"]] = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    skills: Mapped[list["Skill"]] = relationship("Skill", back_populates="user", cascade="all, delete-orphan")
    answer_cache: Mapped[list["AnswerCache"]] = relationship("AnswerCache", back_populates="user", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Profile (one per user)
# ---------------------------------------------------------------------------
class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String)
    city: Mapped[str | None] = mapped_column(String)
    state: Mapped[str | None] = mapped_column(String)
    country: Mapped[str | None] = mapped_column(String)
    work_authorization: Mapped[str | None] = mapped_column(String)  # citizen, h1b, opt, etc.
    requires_sponsorship: Mapped[bool] = mapped_column(Boolean, default=False)
    willing_to_relocate: Mapped[bool] = mapped_column(Boolean, default=False)
    remote_preference: Mapped[str | None] = mapped_column(String)   # remote, hybrid, onsite, any
    notice_period: Mapped[str | None] = mapped_column(String)
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    linkedin_url: Mapped[str | None] = mapped_column(String)
    github_url: Mapped[str | None] = mapped_column(String)
    portfolio_url: Mapped[str | None] = mapped_column(String)
    summary: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship("User", back_populates="profile")


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------
class Education(Base):
    __tablename__ = "education"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    degree: Mapped[str | None] = mapped_column(String)
    field: Mapped[str | None] = mapped_column(String)
    institution: Mapped[str | None] = mapped_column(String)
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    gpa: Mapped[float | None] = mapped_column(Float)

    user: Mapped["User"] = relationship("User", back_populates="education")


# ---------------------------------------------------------------------------
# Experience
# ---------------------------------------------------------------------------
class Experience(Base):
    __tablename__ = "experience"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    company: Mapped[str | None] = mapped_column(String)
    title: Mapped[str | None] = mapped_column(String)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    bullets: Mapped[list] = mapped_column(JSON, default=list)    # list[str]
    tech_stack: Mapped[list] = mapped_column(JSON, default=list)  # list[str]

    user: Mapped["User"] = relationship("User", back_populates="experience")


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String)
    summary: Mapped[str | None] = mapped_column(Text)
    problem: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(Text)
    tech_stack: Mapped[list] = mapped_column(JSON, default=list)  # list[str]
    tags: Mapped[list] = mapped_column(JSON, default=list)         # list[str]
    role: Mapped[str | None] = mapped_column(String)
    link: Mapped[str | None] = mapped_column(String)
    do_not_use: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship("User", back_populates="projects")


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------
class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str | None] = mapped_column(String)    # language, framework, tool, soft
    proficiency: Mapped[str | None] = mapped_column(String) # beginner, intermediate, expert

    user: Mapped["User"] = relationship("User", back_populates="skills")


# ---------------------------------------------------------------------------
# Answer Cache — THE KEY TABLE
# ---------------------------------------------------------------------------
class AnswerCache(Base):
    __tablename__ = "answer_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_question: Mapped[str] = mapped_column(Text, nullable=False)
    question_embedding: Mapped[bytes] = mapped_column(
        # Store as bytes — serialised numpy float32 array
        type_=String,   # SQLite treats BLOB fine via String type; we store hex
        nullable=False,
    )
    question_type: Mapped[str | None] = mapped_column(String)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    tone: Mapped[str | None] = mapped_column(String, default="professional")
    times_used: Mapped[int] = mapped_column(Integer, default=1)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    jobs_used_on: Mapped[list] = mapped_column(JSON, default=list)   # list[str] job IDs
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship("User", back_populates="answer_cache")
