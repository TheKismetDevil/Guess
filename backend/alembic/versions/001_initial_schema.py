"""Initial squashed baseline schema (9 core business tables).

Revision ID: 001
Revises:
Create Date: 2026-11-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=True),
        sa.Column("password_hash", sa.String(length=128), nullable=True),
        sa.Column("qq", sa.String(length=20), nullable=False),
        sa.Column("invite_code", sa.String(length=8), nullable=True),
        sa.Column(
            "is_admin",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_qq", "users", ["qq"], unique=True)
    op.create_index("ix_users_invite_code", "users", ["invite_code"], unique=True)

    op.create_table(
        "horses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sex", sa.String(length=10), nullable=True),
        sa.Column("birth_year", sa.Integer(), nullable=True),
        sa.Column("origin", sa.String(length=100), nullable=True),
        sa.Column("hemisphere", sa.String(length=10), nullable=True),
        sa.Column("location", sa.String(length=100), nullable=True),
        sa.Column("sire", sa.String(length=100), nullable=True),
        sa.Column("damsire", sa.String(length=100), nullable=True),
        sa.Column("previous_result", sa.String(length=100), nullable=True),
        sa.Column("previous_result_date", sa.Date(), nullable=True),
        sa.Column("previous_result_position", sa.Integer(), nullable=True),
        sa.Column("best_win", sa.String(length=100), nullable=True),
        sa.Column("best_win_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_horses_name", "horses", ["name"], unique=True)

    op.create_table(
        "races",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("age_range", sa.String(length=20), nullable=False),
        sa.Column("sex_restriction", sa.String(length=20), nullable=False),
        sa.Column("race_grade", sa.String(length=20), nullable=False),
        sa.Column("country", sa.String(length=50), nullable=False),
        sa.Column("distance", sa.Integer(), nullable=False),
        sa.Column("surface", sa.String(length=20), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'voting'"),
            nullable=False,
        ),
        sa.Column("custom_scoring", sa.JSON(), nullable=True),
        sa.Column(
            "is_hidden",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('voting', 'locked', 'settled')",
            name="ck_races_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "race_horses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("race_id", sa.Integer(), nullable=False),
        sa.Column("horse_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_data", sa.JSON(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("gate", sa.Integer(), nullable=True),
        sa.Column("jockey", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["horse_id"], ["horses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["race_id"], ["races.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_race_horses_race_id", "race_horses", ["race_id"], unique=False)
    op.create_index("ix_race_horses_horse_id", "race_horses", ["horse_id"], unique=False)

    op.create_table(
        "votes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("race_id", sa.Integer(), nullable=False),
        sa.Column("race_horse_id", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["race_horse_id"], ["race_horses.id"]),
        sa.ForeignKeyConstraint(["race_id"], ["races.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "race_id", name="uq_vote_user_race"),
    )
    op.create_index("ix_votes_race_id", "votes", ["race_id"], unique=False)
    op.create_index("ix_votes_race_horse_id", "votes", ["race_horse_id"], unique=False)

    op.create_table(
        "historical_import_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=200), nullable=False),
        sa.Column(
            "imported_races",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "imported_scores",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "updated_races",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "historical_import_changes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("race_id", sa.Integer(), nullable=False),
        sa.Column("before", sa.JSON(), nullable=False),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["historical_import_batches.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_historical_import_changes_batch_id",
        "historical_import_changes",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        "ix_historical_import_changes_race_id",
        "historical_import_changes",
        ["race_id"],
        unique=False,
    )

    op.create_table(
        "historical_races",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_batch_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("age_range", sa.String(length=20), nullable=False),
        sa.Column("sex_restriction", sa.String(length=20), nullable=False),
        sa.Column("race_grade", sa.String(length=20), nullable=False),
        sa.Column("country", sa.String(length=50), nullable=False),
        sa.Column("surface", sa.String(length=20), nullable=False),
        sa.Column("distance", sa.Integer(), nullable=False),
        sa.Column(
            "horse_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["historical_import_batches.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "date", name="uq_historical_races_name_date"),
    )
    op.create_index(
        "ix_historical_races_import_batch_id",
        "historical_races",
        ["import_batch_id"],
        unique=False,
    )

    op.create_table(
        "historical_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("race_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["race_id"],
            ["historical_races.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "race_id",
            "user_id",
            name="uq_historical_scores_race_user",
        ),
    )
    op.create_index(
        "ix_historical_scores_user_id",
        "historical_scores",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_historical_scores_user_id", table_name="historical_scores")
    op.drop_table("historical_scores")

    op.drop_index("ix_historical_races_import_batch_id", table_name="historical_races")
    op.drop_table("historical_races")

    op.drop_index(
        "ix_historical_import_changes_race_id",
        table_name="historical_import_changes",
    )
    op.drop_index(
        "ix_historical_import_changes_batch_id",
        table_name="historical_import_changes",
    )
    op.drop_table("historical_import_changes")

    op.drop_table("historical_import_batches")

    op.drop_index("ix_votes_race_horse_id", table_name="votes")
    op.drop_index("ix_votes_race_id", table_name="votes")
    op.drop_table("votes")

    op.drop_index("ix_race_horses_horse_id", table_name="race_horses")
    op.drop_index("ix_race_horses_race_id", table_name="race_horses")
    op.drop_table("race_horses")

    op.drop_table("races")

    op.drop_index("ix_horses_name", table_name="horses")
    op.drop_table("horses")

    op.drop_index("ix_users_invite_code", table_name="users")
    op.drop_index("ix_users_qq", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
