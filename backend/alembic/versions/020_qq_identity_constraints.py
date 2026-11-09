"""Enforce QQ identity constraints while preserving legacy accounts."""
import sqlalchemy as sa
from alembic import op

revision = '020'
down_revision = '019'
branch_labels = None
depends_on = None


def upgrade():
    # Installations that already ran the original 019 still have its constraint.
    op.execute('ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_users_qq')
    op.add_column('users', sa.Column('legacy_duplicate_qq', sa.Boolean(),
                                     nullable=False, server_default=sa.false()))
    op.execute('''
        UPDATE users SET legacy_duplicate_qq = true
        WHERE id NOT IN (SELECT min(id) FROM users GROUP BY qq)
    ''')
    op.create_index('ix_users_qq', 'users', ['qq'])
    op.create_index('uq_users_qq', 'users', ['qq'], unique=True,
                    postgresql_where=sa.text('NOT legacy_duplicate_qq'))

    # Keep the code assigned to a placeholder, otherwise keep the oldest code.
    op.execute('''
        WITH ranked AS (
            SELECT invite_codes.id, row_number() OVER (
                PARTITION BY bound_qq
                ORDER BY EXISTS (
                    SELECT 1 FROM users
                    WHERE users.qq = invite_codes.bound_qq
                      AND users.invite_code = invite_codes.code
                      AND left(users.password_hash, 13) = '!placeholder:'
                ) DESC, invite_codes.id
            ) AS position
            FROM invite_codes WHERE status = 'unused' AND bound_qq IS NOT NULL
        )
        UPDATE invite_codes SET status = 'disabled'
        WHERE id IN (SELECT id FROM ranked WHERE position > 1)
    ''')
    op.create_index('uq_invite_codes_unused_qq', 'invite_codes', ['bound_qq'], unique=True,
                    postgresql_where=sa.text("status = 'unused' AND bound_qq IS NOT NULL"))


def downgrade():
    op.drop_index('uq_invite_codes_unused_qq', table_name='invite_codes')
    op.drop_index('uq_users_qq', table_name='users')
    op.drop_index('ix_users_qq', table_name='users')
    op.drop_column('users', 'legacy_duplicate_qq')
