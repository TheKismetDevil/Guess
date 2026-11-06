"""Keep before/after snapshots for reviewed historical replacements."""
from alembic import op
import sqlalchemy as sa

revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('historical_import_batches', sa.Column('updated_races', sa.Integer(), nullable=False, server_default='0'))
    op.create_table('historical_import_changes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('batch_id', sa.Integer(), sa.ForeignKey('historical_import_batches.id'), nullable=False),
        sa.Column('race_id', sa.Integer(), nullable=False),
        sa.Column('before', sa.JSON(), nullable=False),
        sa.Column('after', sa.JSON(), nullable=False))
    op.create_index('ix_historical_import_changes_batch_id', 'historical_import_changes', ['batch_id'])
    op.create_index('ix_historical_import_changes_race_id', 'historical_import_changes', ['race_id'])


def downgrade():
    op.drop_table('historical_import_changes')
    op.drop_column('historical_import_batches', 'updated_races')
