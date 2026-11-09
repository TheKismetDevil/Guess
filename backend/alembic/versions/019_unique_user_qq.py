"""Reserve the original QQ uniqueness revision; enforcement now lives in 020."""
from alembic import op

revision = '019'
down_revision = '018'
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    op.execute('ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_users_qq')
