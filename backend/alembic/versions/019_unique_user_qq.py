"""Enforce one account per QQ number."""
from alembic import op

revision = '019'
down_revision = '018'
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint('uq_users_qq', 'users', ['qq'])


def downgrade():
    op.drop_constraint('uq_users_qq', 'users', type_='unique')
