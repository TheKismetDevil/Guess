"""Track historical imports and preserve existing results as a legacy batch."""
from alembic import op
import sqlalchemy as sa

revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('historical_import_batches',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('filename', sa.String(200), nullable=False),
        sa.Column('imported_races', sa.Integer(), server_default='0', nullable=False),
        sa.Column('imported_scores', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('undone_at', sa.DateTime(timezone=True)))
    op.add_column('historical_races', sa.Column('import_batch_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_historical_races_batch', 'historical_races', 'historical_import_batches', ['import_batch_id'], ['id'])
    op.create_index('ix_historical_races_import_batch_id', 'historical_races', ['import_batch_id'])
    op.execute("INSERT INTO historical_import_batches (filename, imported_races, imported_scores) SELECT '既有历史成绩', (SELECT count(*) FROM historical_races), (SELECT count(*) FROM historical_scores) WHERE EXISTS (SELECT 1 FROM historical_races)")
    op.execute('UPDATE historical_races SET import_batch_id = (SELECT id FROM historical_import_batches ORDER BY id LIMIT 1)')


def downgrade():
    op.drop_index('ix_historical_races_import_batch_id', table_name='historical_races')
    op.drop_constraint('fk_historical_races_batch', 'historical_races', type_='foreignkey')
    op.drop_column('historical_races', 'import_batch_id')
    op.drop_table('historical_import_batches')
