"""create race and race_horse tables

Revision ID: 004
Revises: 003
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create grade_enum type if not exists (raw SQL to handle idempotency)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'grade_enum') THEN
            CREATE TYPE grade_enum AS ENUM ('G1', 'G2_JPN1', 'YOUNG_G1', 'CUSTOM');
        END IF;
    END
    $$;
    """)

    # Create race_status_enum type if not exists (uppercase to match SQLAlchemy default behavior)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'race_status_enum') THEN
            CREATE TYPE race_status_enum AS ENUM ('VOTING', 'LOCKED', 'SETTLED');
        END IF;
    END
    $$;
    """)

    # Declare enums with create_type=False to prevent duplicate creation in create_table
    grade_enum = ENUM("G1", "G2_JPN1", "YOUNG_G1", "CUSTOM", name="grade_enum", create_type=False)
    status_enum = ENUM("VOTING", "LOCKED", "SETTLED", name="race_status_enum", create_type=False)

    # Create races table
    op.create_table(
        "races",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "grade",
            grade_enum,
            nullable=False,
        ),
        sa.Column(
            "status",
            status_enum,
            nullable=False,
            server_default=sa.text("'VOTING'"),
        ),
        sa.Column("custom_scoring", sa.JSON(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create race_horses table
    op.create_table(
        "race_horses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("race_id", sa.Integer(), nullable=False),
        sa.Column("horse_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_data", sa.JSON(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["race_id"], ["races.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["horse_id"], ["horses.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_race_horses_race_id"), "race_horses", ["race_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_race_horses_race_id"), table_name="race_horses")
    op.drop_table("race_horses")
    op.drop_table("races")

    op.execute("DROP TYPE IF EXISTS race_status_enum")
    op.execute("DROP TYPE IF EXISTS grade_enum")
