"""Vote API endpoints — voting and lock operations."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.vote import VoteCreate, VoteListEntry, VoteResponse
from app.services import vote_service
from app.services.avatar_service import avatar_key

router = APIRouter(prefix="/api/v1/races", tags=["votes"])


@router.post("/{race_id}/votes")
async def cast_vote(
    race_id: int,
    data: VoteCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cast or modify a vote on a race. Requires authentication.
    Admin accounts are not allowed to vote.
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "NOT_AUTHENTICATED", "message": "请先登录"},
        )
    if current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ADMIN_CANNOT_VOTE", "message": "管理员无法参与投票"},
        )

    vote, sc = await vote_service.create_or_update_vote(
        db=db,
        race_id=race_id,
        user_id=current_user.id,
        race_horse_id=data.race_horse_id,
    )

    # Vote is already eager-loaded with race_horse_rel by the service
    horse_name = vote_service.resolve_horse_name(vote)

    response_data = VoteResponse(
        id=vote.id,
        user_id=vote.user_id,
        race_id=vote.race_id,
        race_horse_id=vote.race_horse_id,
        horse_name=horse_name,
        created_at=vote.created_at,
        updated_at=vote.updated_at,
    )

    response.status_code = sc
    return {"data": response_data.model_dump()}


@router.get("/{race_id}/votes")
async def list_votes(
    race_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get all votes for a race. Public endpoint."""
    votes = await vote_service.get_race_votes(db, race_id)

    entries = [
        VoteListEntry(
            user_id=v.user_id,
            username=v.user.username if v.user else "unknown",
            avatar_key=avatar_key(v.user.qq) if v.user else None,
            race_horse_id=v.race_horse_id,
            horse_name=vote_service.resolve_horse_name(v),
            points=v.points,
            created_at=v.created_at,
        )
        for v in votes
    ]

    return {"data": [e.model_dump() for e in entries]}


@router.delete("/{race_id}/votes")
async def cancel_vote(
    race_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a user's vote on a race. Requires authentication."""
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "NOT_AUTHENTICATED", "message": "请先登录"},
        )
    if current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ADMIN_CANNOT_VOTE", "message": "管理员无法参与投票"},
        )

    await vote_service.delete_vote(
        db=db,
        race_id=race_id,
        user_id=current_user.id,
    )

    return {"data": {"message": "投票已取消"}}


@router.post("/{race_id}/lock")
async def lock_race(
    race_id: int,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Lock a race's voting. Admin only."""
    race = await vote_service.lock_race(db, race_id)
    return {
        "data": {
            "id": race.id,
            "name": race.name,
            "status": race.status.value,
            "updated_at": race.updated_at.isoformat(),
        }
    }
