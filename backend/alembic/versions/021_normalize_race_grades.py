"""Normalize race grades and backfill scores under the new G2/JPN1 rules."""
from alembic import op

revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None

_SUPPORTED_GRADES = "'G1', 'G2', 'JPN1', '其他', '自定义'"


def _historical_tags(grade, surface):
    # Match the workbook importer for grades and surfaces stored by older imports.
    canonical_grade = f"translate(upper({grade}), '·・.- ', '')"
    is_steeplechase = f"{surface} LIKE '障碍%'"
    return (
        f"""CASE
            WHEN {is_steeplechase} THEN '其他'
            WHEN {canonical_grade} IN ('G1', 'G2', 'JPN1') THEN {canonical_grade}
            WHEN {grade} = '自定义' THEN '自定义'
            ELSE '其他'
        END""",
        f"CASE WHEN {is_steeplechase} THEN '障碍' ELSE {surface} END",
    )


def upgrade():
    op.execute(f"""
        UPDATE races
        SET race_grade = '其他', custom_scoring = NULL
        WHERE race_grade NOT IN ({_SUPPORTED_GRADES})
    """)
    grade, surface = _historical_tags('race_grade', 'surface')
    op.execute(f"""
        UPDATE historical_races
        SET race_grade = {grade}, surface = {surface}
        WHERE (race_grade, surface) IS DISTINCT FROM ({grade}, {surface})
    """)
    for column in ('before', 'after'):
        snapshot = f'CAST({column} AS jsonb)'
        metadata = f"({snapshot} -> 'metadata')"
        old_grade = f"({metadata} ->> 'race_grade')"
        old_surface = f"({metadata} ->> 'surface')"
        grade, surface = _historical_tags(old_grade, old_surface)
        op.execute(f"""
            UPDATE historical_import_changes
            SET {column} = CAST(jsonb_set({snapshot}, '{{metadata}}',
                {metadata} || jsonb_build_object('race_grade', {grade}, 'surface', {surface})) AS json)
            WHERE ({old_grade}, {old_surface}) IS DISTINCT FROM ({grade}, {surface})
        """)

    # G2, JPN1 and 其他 share a points table with no penalties.
    op.execute("""
        WITH recalculated AS (
            SELECT votes.id, votes.points AS old_points,
                CASE race_horses.position WHEN 1 THEN 5 WHEN 2 THEN 3 WHEN 3 THEN 1
                    ELSE 0 END AS new_points
            FROM votes
            JOIN races ON races.id = votes.race_id
            LEFT JOIN race_horses ON race_horses.id = votes.race_horse_id
                AND race_horses.race_id = races.id
            WHERE races.status = 'SETTLED' AND races.race_grade IN ('G2', 'JPN1', '其他')
        ), changed AS (
            UPDATE votes SET points = recalculated.new_points
            FROM recalculated
            WHERE votes.id = recalculated.id AND votes.points IS DISTINCT FROM recalculated.new_points
            RETURNING votes.race_id, votes.id, votes.user_id, recalculated.old_points, votes.points
        )
        INSERT INTO score_change_logs (race_id, vote_id, user_id, old_points, new_points)
        SELECT race_id, id, user_id, old_points, points FROM changed
    """)


def downgrade():
    pass
