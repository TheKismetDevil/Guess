"""Store imported historical results independently from live races."""
from alembic import op
import sqlalchemy as sa

revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('historical_races',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('age_range', sa.String(20), nullable=False),
        sa.Column('sex_restriction', sa.String(20), nullable=False),
        sa.Column('race_grade', sa.String(20), nullable=False),
        sa.Column('country', sa.String(50), nullable=False),
        sa.Column('surface', sa.String(20), nullable=False),
        sa.Column('distance', sa.Integer(), nullable=False),
        sa.Column('horse_count', sa.Integer(), nullable=False),
        sa.UniqueConstraint('name', 'date'))
    op.create_table('historical_scores',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('race_id', sa.Integer(), sa.ForeignKey('historical_races.id', ondelete='CASCADE'), nullable=False),
        sa.Column('qq', sa.String(20), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.UniqueConstraint('race_id', 'qq'))
    op.create_index('ix_historical_scores_qq', 'historical_scores', ['qq'])

def downgrade():
    op.drop_index('ix_historical_scores_qq', table_name='historical_scores')
    op.drop_table('historical_scores')
    op.drop_table('historical_races')
