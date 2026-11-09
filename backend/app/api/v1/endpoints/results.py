"""Result entry API endpoints — drag-sort result submission."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.schemas.result import ResultEntry, ResultEntryResponse
from app.services import result_service

router = APIRouter(prefix="/api/v1/races", tags=["results"])


@router.put("/{race_id}/results")
async def submit_results(
    race_id: int,
    data: ResultEntry,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Submit race results via drag-sorted positions. Admin only.

    Transitions race from locked to settled, calculating scores for all voters.
    If race is already settled, re-settles with new positions.
    """
    result = await result_service.submit_results(db, race_id, data)
    return {
        "data": ResultEntryResponse(
            race_id=result["race_id"],
            status=result["status"],
            scores=result["scores"],
        ).model_dump()
    }
