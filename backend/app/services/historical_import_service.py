"""Import the historical-score workbook without creating live races."""
from datetime import date, datetime
from io import BytesIO
from openpyxl import load_workbook
from sqlalchemy import select
from fastapi import HTTPException
from app.models.historical_score import HistoricalRace, HistoricalScore
from app.models.race import Race
from app.models.user import User


def invalid(message):
    return HTTPException(status_code=400, detail={'code': 'INVALID_WORKBOOK', 'message': message})


async def import_workbook(db, content: bytes):
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        rows = list(workbook['历史得分'].values)
        meta_rows = list(workbook['赛事资料'].values)
    except Exception as exc:
        raise invalid('无法读取工作簿，请检查文件及工作表名称') from exc
    if not rows or tuple(rows[0][:2]) != ('用户名', 'QQ号') or not meta_rows or meta_rows[0][0] != '比赛名称':
        raise invalid('工作表格式不正确')
    names = [str(x).strip() for x in rows[0][2:] if x is not None]
    if not names or len(names) != len(set(names)):
        raise invalid('赛事列为空或存在重复名称')
    metadata = {}
    for row in meta_rows[1:]:
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
            if distance <= 0 or horse_count < 0 or distance != float(row[7]) or (row[8] and horse_count != float(row[8])):
                raise ValueError()
            sex = {'牝马': '牝限', '牡牝': '牡牝限', '牡马': '牡限'}.get(row[3], row[3])
            grade = {'Jpn1': 'JPN1', 'Jpn2': 'JPN2'}.get(row[4], row[4])
            country = {'沙特阿拉伯': '沙特'}.get(row[5], row[5])
            surface = '障碍' if str(row[6]).startswith('障碍') else row[6]
            metadata[name] = dict(name=name, date=when, age_range=row[2], sex_restriction=sex, race_grade=grade, country=country, surface=surface, distance=distance, horse_count=horse_count)
        except (ValueError, TypeError, IndexError) as exc:
            raise invalid(f'赛事资料不完整或格式错误：{name}') from exc
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
        if not name or not qq.isdigit() or len(qq) > 20:
            raise invalid(f'历史得分第 {index} 行需要用户名和有效 QQ 号')
        if qq in seen_qq:
            raise invalid(f'QQ 号重复：{qq}')
        seen_qq.add(qq)
        points = []
        for value in row[2:2 + len(names)]:
            if value is None or value == '':
                points.append(None)
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
                raise invalid(f'历史得分第 {index} 行包含无效分数')
            else:
                points.append(int(value))
        participants.append((name, qq, points))
    registered = (await db.execute(select(User.qq))).scalars().all()
    ambiguous = {qq for qq in seen_qq if registered.count(qq) > 1}
    if ambiguous:
        raise invalid('存在多个账户使用同一 QQ，请先处理：' + '、'.join(sorted(ambiguous)))
    existing_live = set((await db.execute(select(Race.name, Race.date))).all())
    existing_history = set((await db.execute(select(HistoricalRace.name, HistoricalRace.date))).all())
    inserted, skipped, count = 0, [], 0
    for col, name in enumerate(names):
        item = metadata[name]
        if (name, item['date']) in existing_live or (name, item['date']) in existing_history:
            skipped.append(name)
            continue
        race = HistoricalRace(**item)
        db.add(race)
        await db.flush()
        for display_name, qq, points in participants:
            if col < len(points) and points[col] is not None:
                db.add(HistoricalScore(race_id=race.id, qq=qq, display_name=display_name, points=points[col]))
                count += 1
        inserted += 1
    await db.flush()
    return {'imported_races': inserted, 'imported_scores': count, 'skipped_races': skipped}
