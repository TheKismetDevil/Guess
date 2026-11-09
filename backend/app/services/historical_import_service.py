"""Import the historical-score workbook without creating live races."""
from datetime import date, datetime
from io import BytesIO
import hashlib
import json
import math
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from fastapi import HTTPException
from app.models.historical_score import HistoricalImportBatch, HistoricalImportChange, HistoricalRace, HistoricalScore
from app.models.race import Race
from app.models.user import User
from app.services.historical_snapshot import snapshot, current_snapshot, apply_snapshot, differences


def invalid(message):
    return HTTPException(status_code=400, detail={'code': 'INVALID_WORKBOOK', 'message': message})


def parse_workbook(content: bytes):
    workbook = None
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        rows = list(workbook['历史得分'].values)
        meta_rows = list(workbook['赛事资料'].values)
    except Exception as exc:
        raise invalid('无法读取工作簿，请检查文件及工作表名称') from exc
    finally:
        if workbook is not None:
            workbook.close()
    if not rows or tuple(rows[0][:2]) != ('用户名', 'QQ号') or not meta_rows or meta_rows[0][0] != '比赛名称':
        raise invalid('工作表格式不正确')
    names = [str(x).strip() if x is not None else '' for x in rows[0][2:]]
    while names and not names[-1]:
        names.pop()
    if not names or any(not name or len(name) > 200 for name in names) or len(names) != len(set(names)):
        raise invalid('赛事列为空或存在重复名称')
    metadata = {}
    for row_index, row in enumerate(meta_rows[1:], 2):
        if not row[0]:
            continue
        name = str(row[0]).strip()
        if name in metadata:
            raise invalid(f'赛事资料中名称重复：{name}')
        try:
            when = row[1].date() if isinstance(row[1], datetime) else row[1] if isinstance(row[1], date) else date.fromisoformat(str(row[1]).strip())
            if any(row[i] is None or not str(row[i]).strip() for i in range(2, 8)):
                raise ValueError()
            distance = int(row[7]); horse_count = int(row[8] or 0)
            if isinstance(row[7], bool) or isinstance(row[8], bool) or not 0 < distance <= 2147483647 or not 0 <= horse_count <= 2147483647 or distance != float(row[7]) or (row[8] and horse_count != float(row[8])):
                raise ValueError()
            tags = [str(value).strip() for value in row[2:7]]
            if any(len(value) > limit for value, limit in zip(tags, [20, 20, 20, 50, 20])):
                raise ValueError()
            age, sex, grade, country, surface = tags
            sex = {'牝马': '牝限', '牡牝': '牡牝限', '牡马': '牡限'}.get(sex, sex)
            grade = {'Jpn1': 'JPN1', 'Jpn2': 'JPN2'}.get(grade, grade)
            # Steeplechase J·G1 is not a separate grade category; treat it as 自定义.
            if grade.upper().replace('·', '').replace('・', '').replace('.', '').replace('-', '').replace(' ', '') == 'JG1':
                grade = '自定义'
            country = {'沙特阿拉伯': '沙特'}.get(country, country)
            surface = '障碍' if surface.startswith('障碍') else surface
            metadata[name] = dict(name=name, date=when, age_range=age, sex_restriction=sex, race_grade=grade, country=country, surface=surface, distance=distance, horse_count=horse_count)
        except (ValueError, TypeError, IndexError, OverflowError) as exc:
            raise invalid(f'赛事资料第 {row_index} 行（{name}）不完整或格式错误') from exc
    if set(names) != set(metadata):
        raise invalid('历史得分与赛事资料的比赛名称不一致')
    seen_qq = set()
    participants = []
    for index, row in enumerate(rows[1:], 2):
        if not any(value is not None and value != '' for value in row):
            continue
        # The workbook may end with an aggregate row, which is not a participant.
        if str(row[0] or '').strip() in ('合计', '总计') and not row[1]:
            continue
        name = str(row[0] or '').strip()
        qq = str(row[1] or '').strip()
        if not name or len(name) > 100 or not qq.isdigit() or len(qq) > 20:
            raise invalid(f'历史得分 A{index}/B{index} 需要用户名（不超过100字）和有效 QQ 号')
        if qq in seen_qq:
            raise invalid(f'QQ 号重复：{qq}')
        seen_qq.add(qq)
        points = []
        for col, value in enumerate(row[2:2 + len(names)], 3):
            if value is None or value == '':
                points.append(None)
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or int(value) != value or not -2147483648 <= value <= 2147483647:
                raise invalid(f'历史得分 {get_column_letter(col)}{index} 包含无效分数，请填写整数或留空')
            else:
                points.append(int(value))
        participants.append((name, qq, points))
    return names, metadata, participants


async def prepare_import(db, content: bytes, lock=False, *, skip_identical=True, skip_empty=True):
    names, metadata, participants = parse_workbook(content)
    seen_qq = {qq for _, qq, _ in participants}
    registered = (await db.execute(select(User.qq))).scalars().all()
    ambiguous = {qq for qq in seen_qq if registered.count(qq) > 1}
    if ambiguous:
        raise invalid('存在多个账户使用同一 QQ，请先处理：' + '、'.join(sorted(ambiguous)))
    existing_live = set((await db.execute(select(Race.name, Race.date))).all())
    query = select(HistoricalRace).order_by(HistoricalRace.id)
    if lock:
        query = query.with_for_update()
    existing_history = {(r.name, r.date): r for r in (await db.execute(query)).scalars()}
    races, states = [], {}
    for col, name in enumerate(names):
        item = metadata[name]
        history = existing_history.get((name, item['date']))
        incoming = snapshot(item, [dict(qq=qq, display_name=display_name, points=p[col])
            for display_name, qq, p in participants if col < len(p) and p[col] is not None])
        before = await current_snapshot(db, history) if history else None
        diff = differences(before, incoming) if before else []
        live = (name, item['date']) in existing_live
        if live:
            action, reason = 'skip', '已有在线比赛'
        elif skip_empty and not incoming['scores']:
            action, reason = 'skip', '无成绩，不导入'
        elif before is not None and not diff:
            action, reason = ('skip', '内容完全相同') if skip_identical else ('reimport', '内容相同，重新导入')
        else:
            action, reason = ('conflict' if before is not None else 'import'), ''
        races.append({'name': name, 'date': item['date'].isoformat(), 'race_id': history.id if history else None,
            'action': action, 'reason': reason,
            'score_count': len(incoming['scores']), 'differences': diff,
            'state_token': hashlib.sha256(json.dumps(before, ensure_ascii=False, sort_keys=True).encode()).hexdigest()})
        states[name] = (history, before, incoming)
    options = {'skip_identical': skip_identical, 'skip_empty': skip_empty}
    digest = hashlib.sha256(content + json.dumps({'races': races, 'options': options}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    preview = {'races': races, 'participants': len(participants),
        'imported_races': sum(r['action'] == 'import' for r in races),
        'imported_scores': sum(r['score_count'] for r in races if r['action'] == 'import'),
        'conflicting_races': sum(r['action'] == 'conflict' for r in races),
        'reimported_races': sum(r['action'] == 'reimport' for r in races),
        'options': options,
        'skipped_races': [r['name'] for r in races if r['action'] == 'skip'], 'preview_token': digest}
    return preview, states


async def preview_workbook(db, content: bytes, *, skip_identical=True, skip_empty=True):
    return (await prepare_import(db, content, skip_identical=skip_identical, skip_empty=skip_empty))[0]


async def import_workbook(db, content: bytes, filename='历史得分.xlsx', preview_token=None, decisions=None, *, skip_identical=True, skip_empty=True):
    preview, states = await prepare_import(db, content, lock=True, skip_identical=skip_identical, skip_empty=skip_empty)
    if preview_token is not None and preview_token != preview['preview_token']:
        raise HTTPException(status_code=409, detail={'code': 'PREVIEW_CHANGED', 'message': '数据已变化，请重新预览后导入'})
    decisions = decisions or {}
    conflicts = {str(r['race_id']) for r in preview['races'] if r['action'] == 'conflict'}
    if set(decisions) != conflicts or any(value not in ('keep', 'replace') for value in decisions.values()):
        raise HTTPException(400, detail={'code': 'DECISIONS_REQUIRED', 'message': '请为每场有差异的历史比赛选择保留已有或使用本次文件'})
    if conflicts and preview_token is None:
        raise HTTPException(400, detail={'code': 'PREVIEW_REQUIRED', 'message': '请先预览差异再确认更新'})
    updated = sum(value == 'replace' for value in decisions.values()) + preview['reimported_races']
    batch = None
    if preview['imported_races'] or updated:
        batch = HistoricalImportBatch(filename=filename[:200], imported_races=preview['imported_races'],
            imported_scores=preview['imported_scores'], updated_races=updated)
        db.add(batch)
        await db.flush()
    for item in preview['races']:
        race, before, incoming = states[item['name']]
        if item['action'] == 'skip' or (item['action'] == 'conflict' and decisions[str(item['race_id'])] == 'keep'):
            continue
        if item['action'] == 'import':
            race = HistoricalRace(**{**incoming['metadata'], 'date': date.fromisoformat(incoming['metadata']['date'])}, import_batch_id=batch.id)
            db.add(race)
            await db.flush()
        else:
            db.add(HistoricalImportChange(batch_id=batch.id, race_id=race.id, before=before, after=incoming))
        await apply_snapshot(db, race, incoming)
    await db.flush()
    return {key: preview[key] for key in ('imported_races', 'imported_scores')} | {
        'updated_races': updated, 'skipped_races': preview['skipped_races'] + [r['name'] for r in preview['races']
            if r['action'] == 'conflict' and decisions[str(r['race_id'])] == 'keep'],
        'batch_id': batch.id if batch else None}
