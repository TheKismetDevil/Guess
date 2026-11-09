"""Normalize dropped race grades and steeplechase races to 其他."""
from alembic import op

revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None

_SUPPORTED_GRADES = "'G1', 'G2', 'JPN1', '其他', '自定义'"


def upgrade():
    op.execute(f"""
        UPDATE races
        SET race_grade = '其他', custom_scoring = NULL
        WHERE race_grade NOT IN ({_SUPPORTED_GRADES})
    """)
    op.execute(f"""
        UPDATE historical_races
        SET race_grade = '其他'
        WHERE surface = '障碍' OR race_grade NOT IN ({_SUPPORTED_GRADES})
    """)
    op.execute(f"""
        UPDATE historical_import_changes
        SET before = CAST(jsonb_set(CAST(before AS jsonb), '{{metadata,race_grade}}', '"其他"') AS json)
        WHERE CAST(before AS jsonb) -> 'metadata' ->> 'surface' = '障碍'
           OR CAST(before AS jsonb) -> 'metadata' ->> 'race_grade' NOT IN ({_SUPPORTED_GRADES})
    """)
    op.execute(f"""
        UPDATE historical_import_changes
        SET after = CAST(jsonb_set(CAST(after AS jsonb), '{{metadata,race_grade}}', '"其他"') AS json)
        WHERE CAST(after AS jsonb) -> 'metadata' ->> 'surface' = '障碍'
           OR CAST(after AS jsonb) -> 'metadata' ->> 'race_grade' NOT IN ({_SUPPORTED_GRADES})
    """)


def downgrade():
    pass
