"""Admin API endpoints — invite code management."""

import json
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.schemas.invite_code import InviteCodeCreate, InviteCodeResponse
from app.services import invite_code_service
from app.services import historical_management_service as history
from app.schemas.historical import HistoricalScoreUpdate

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


async def read_workbook(request: Request):
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail={'code': 'FILE_TOO_LARGE', 'message': '文件不能超过 10 MB'})
    return bytes(content)


@router.post('/historical-scores/preview')
async def preview_historical_scores(request: Request, skip_identical: bool = True, skip_empty: bool = True,
    db: AsyncSession = Depends(get_db), _admin=Depends(get_current_admin)):
    from app.services.historical_import_service import preview_workbook
    return {'data': await preview_workbook(db, await read_workbook(request), skip_identical=skip_identical, skip_empty=skip_empty)}


@router.post('/historical-scores')
async def import_historical_scores(request: Request, filename: str = Query('历史得分.xlsx', max_length=200),
    preview_token: str | None = None, decisions: str | None = None,
    skip_identical: bool = True, skip_empty: bool = True,
    db: AsyncSession = Depends(get_db), _admin=Depends(get_current_admin)):
    from app.services.historical_import_service import import_workbook
    try:
        choices = json.loads(decisions) if decisions is not None else {}
        if not isinstance(choices, dict) or any(not isinstance(v, str) for v in choices.values()):
            raise ValueError()
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, detail={'code': 'INVALID_DECISIONS', 'message': '差异选择格式错误，请重新预览'}) from exc
    try:
        return {'data': await import_workbook(db, await read_workbook(request), filename, preview_token, choices,
            skip_identical=skip_identical, skip_empty=skip_empty)}
    except IntegrityError as exc:
        raise HTTPException(409, detail={'code': 'IMPORT_CONFLICT', 'message': '比赛已被其他请求导入，请重新预览'}) from exc


@router.get('/historical-batches')
async def historical_batches(db: AsyncSession = Depends(get_db), _admin=Depends(get_current_admin)):
    return {'data': await history.list_batches(db)}


@router.get('/historical-batches/{batch_id}/races')
async def historical_batch_races(batch_id: int, db: AsyncSession = Depends(get_db), _admin=Depends(get_current_admin)):
    return {'data': await history.batch_races(db, batch_id)}


@router.post('/historical-batches/{batch_id}/undo')
async def undo_historical_batch(batch_id: int, db: AsyncSession = Depends(get_db), _admin=Depends(get_current_admin)):
    return {'data': await history.undo_batch(db, batch_id)}


@router.get('/historical-races/{race_id}/scores')
async def historical_race_scores(race_id: int, db: AsyncSession = Depends(get_db), _admin=Depends(get_current_admin)):
    return {'data': await history.race_scores(db, race_id)}


@router.patch('/historical-scores/{score_id}')
async def update_historical_score(score_id: int, data: HistoricalScoreUpdate, db: AsyncSession = Depends(get_db), _admin=Depends(get_current_admin)):
    return {'data': await history.update_score(db, score_id, data.points, data.expected_points)}


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
