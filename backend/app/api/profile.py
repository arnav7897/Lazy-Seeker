"""Profile CRUD routes: profile fields + education, experience, projects, skills."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, Profile, Education, Experience, Project, Skill
from app.schemas.schemas import (
    ProfileOut, ProfileUpdate,
    EducationCreate, EducationOut,
    ExperienceCreate, ExperienceOut,
    ProjectCreate, ProjectUpdate, ProjectOut,
    SkillCreate, SkillOut,
)

router = APIRouter(prefix="/profile", tags=["profile"])


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
@router.get("", response_model=ProfileOut)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Profile).where(Profile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("", response_model=ProfileOut)
async def update_profile(
    body: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Profile).where(Profile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = Profile(user_id=current_user.id)
        db.add(profile)

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------
@router.get("/education", response_model=list[EducationOut])
async def list_education(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Education).where(Education.user_id == current_user.id))
    return result.scalars().all()


@router.post("/education", response_model=EducationOut, status_code=201)
async def add_education(
    body: EducationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    edu = Education(user_id=current_user.id, **body.model_dump())
    db.add(edu)
    await db.commit()
    await db.refresh(edu)
    return edu


@router.delete("/education/{edu_id}", status_code=204)
async def delete_education(
    edu_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Education).where(Education.id == edu_id, Education.user_id == current_user.id)
    )
    edu = result.scalar_one_or_none()
    if not edu:
        raise HTTPException(status_code=404, detail="Education record not found")
    await db.delete(edu)
    await db.commit()


# ---------------------------------------------------------------------------
# Experience
# ---------------------------------------------------------------------------
@router.get("/experience", response_model=list[ExperienceOut])
async def list_experience(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Experience).where(Experience.user_id == current_user.id))
    return result.scalars().all()


@router.post("/experience", response_model=ExperienceOut, status_code=201)
async def add_experience(
    body: ExperienceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exp = Experience(user_id=current_user.id, **body.model_dump())
    db.add(exp)
    await db.commit()
    await db.refresh(exp)
    return exp


@router.delete("/experience/{exp_id}", status_code=204)
async def delete_experience(
    exp_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Experience).where(Experience.id == exp_id, Experience.user_id == current_user.id)
    )
    exp = result.scalar_one_or_none()
    if not exp:
        raise HTTPException(status_code=404, detail="Experience record not found")
    await db.delete(exp)
    await db.commit()


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
@router.get("/projects", response_model=list[ProjectOut])
async def list_projects(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.user_id == current_user.id))
    return result.scalars().all()


@router.post("/projects", response_model=ProjectOut, status_code=201)
async def add_project(
    body: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = Project(user_id=current_user.id, **body.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.put("/projects/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    await db.commit()


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------
@router.get("/skills", response_model=list[SkillOut])
async def list_skills(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Skill).where(Skill.user_id == current_user.id))
    return result.scalars().all()


@router.post("/skills", response_model=SkillOut, status_code=201)
async def add_skill(
    body: SkillCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    skill = Skill(user_id=current_user.id, **body.model_dump())
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return skill


@router.delete("/skills/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.user_id == current_user.id)
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    await db.delete(skill)
    await db.commit()
