"""Admin API endpoints — invite code management."""

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.schemas.invite_code import InviteCodeCreate, InviteCodeResponse
from app.services import invite_code_service

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post('/historical-scores')
async def import_historical_scores(request: Request, db: AsyncSession = Depends(get_db), _admin=Depends(get_current_admin)):
    from app.services.historical_import_service import import_workbook
    content = await request.body()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail={'code': 'FILE_TOO_LARGE', 'message': '文件不能超过 10 MB'})
    return {'data': await import_workbook(db, content)}


@router.get("/invite-codes", response_model=dict)
async def list_invite_codes(
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Get all invite codes, optionally filtered by search."""
    codes = await invite_code_service.get_invite_codes(db, search)
    return {"data": [InviteCodeResponse.model_validate(c) for c in codes]}


@router.post("/invite-codes", status_code=201, response_model=dict)
async def create_invite_code(
    request: InviteCodeCreate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Generate a new invite code bound to a QQ number."""
    code = await invite_code_service.create_invite_code(db, request.qq)
    return {"data": InviteCodeResponse.model_validate(code)}


@router.delete("/invite-codes/{code}", status_code=204)
async def delete_invite_code(
    code: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Delete an invite code and cascade delete its bound user and votes."""
    await invite_code_service.delete_invite_code_cascade(db, code)
