"""Horse API endpoints — CRUD for the horse library."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_user
from app.core.database import get_db
from app.schemas.horse import HorseCreate, HorseResponse, HorseUpdate
from app.services import horse_service

router = APIRouter(prefix="/api/v1/horses", tags=["horses"])


class UpdateBestWinRequest(BaseModel):
    race_id: int


@router.get("", response_model=dict)
async def list_horses(
    name: str | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get all horses. Supports optional ?name=xxx fuzzy search."""
    horses = await horse_service.get_horses(db, name)
    return {"data": [HorseResponse.model_validate(h) for h in horses]}


@router.get("/origins/stats", response_model=dict)
async def list_origins_stats(
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get origin (country) usage frequency statistics with hemisphere info."""
    stats = await horse_service.get_origins_stats(db)
    return {"data": stats}


@router.get("/locations/stats", response_model=dict)
async def list_locations_stats(
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get location (training stable) usage frequency statistics."""
    stats = await horse_service.get_locations_stats(db)
    return {"data": stats}


@router.get("/{horse_id}", response_model=dict)
async def get_horse(
    horse_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get a single horse by ID."""
    horse = await horse_service.get_horse(db, horse_id)
    if horse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "马匹不存在"},
        )
    return {"data": HorseResponse.model_validate(horse)}


@router.post("", status_code=201, response_model=dict)
async def create_horse(
    data: HorseCreate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Create a new horse. Admin only."""
    horse = await horse_service.create_horse(db, data)
    return {"data": HorseResponse.model_validate(horse)}


@router.patch("/{horse_id}", response_model=dict)
async def update_horse(
    horse_id: int,
    data: HorseUpdate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Update a horse's attributes. Admin only."""
    horse = await horse_service.update_horse(db, horse_id, data)
    return {"data": HorseResponse.model_validate(horse)}


@router.delete("/{horse_id}", status_code=204)
async def delete_horse(
    horse_id: int,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Delete a horse. Admin only."""
    await horse_service.delete_horse(db, horse_id)


@router.post("/origins/{origin}/toggle-hemisphere", response_model=dict)
async def toggle_origin_hemisphere(
    origin: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Toggle hemisphere for all horses with the given origin. Admin only."""
    result = await horse_service.toggle_hemisphere(db, origin)
    return {"data": result}


@router.post("/{horse_id}/update-best-win", response_model=dict)
async def update_horse_best_win(
    horse_id: int,
    data: UpdateBestWinRequest,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Update a horse's best_win to the specified race. Admin only."""
    horse = await horse_service.update_best_win(db, horse_id, data.race_id)
    return {"data": HorseResponse.model_validate(horse)}
