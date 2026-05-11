"""Answer Cache API routes."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, AnswerCache
from app.schemas.schemas import (
    AnswerCacheCreate, AnswerCacheUpdate, AnswerCacheOut, CacheMatchResponse
)
from app.services.cache_service import cache_service

router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/answers", response_model=list[AnswerCacheOut])
async def list_answers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AnswerCache)
        .where(AnswerCache.user_id == current_user.id)
        .order_by(AnswerCache.times_used.desc(), AnswerCache.created_at.desc())
    )
    return result.scalars().all()


@router.get("/answers/match", response_model=CacheMatchResponse)
async def match_answer(
    question: str = Query(..., description="The incoming application question to match"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await cache_service.find_similar(current_user.id, question, db)
    return CacheMatchResponse(
        hit=result.hit,
        score=result.score,
        needs_review=result.needs_review,
        answer=result.answer,
        suggestion=result.suggestion,
    )


@router.post("/answers", response_model=AnswerCacheOut, status_code=201)
async def store_answer(
    body: AnswerCacheCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await cache_service.store_answer(
        user_id=current_user.id,
        question=body.question_text,
        answer=body.answer_text,
        question_type=body.question_type,
        tone=body.tone,
        db=db,
    )
    return entry


@router.put("/answers/{cache_id}", response_model=AnswerCacheOut)
async def update_answer(
    cache_id: str,
    body: AnswerCacheUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await cache_service.update_answer(cache_id, current_user.id, body.answer_text, db)
    if not entry:
        raise HTTPException(status_code=404, detail="Cache entry not found")
    return entry


@router.delete("/answers/{cache_id}", status_code=204)
async def delete_answer(
    cache_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await cache_service.delete_answer(cache_id, current_user.id, db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Cache entry not found")


@router.put("/answers/{cache_id}/pin", response_model=AnswerCacheOut)
async def pin_answer(
    cache_id: str,
    pinned: bool = Query(True, description="True to pin, False to unpin"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await cache_service.pin_answer(cache_id, current_user.id, pinned, db)
    if not entry:
        raise HTTPException(status_code=404, detail="Cache entry not found")
    return entry
