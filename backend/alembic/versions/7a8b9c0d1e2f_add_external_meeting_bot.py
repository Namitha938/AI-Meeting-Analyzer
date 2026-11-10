"""add external meeting bot fields

Revision ID: 7a8b9c0d1e2f
Revises: 6f7a8b9c0d1e
Create Date: 2026-11-03 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '7a8b9c0d1e2f'
down_revision = '6f7a8b9c0d1e'
branch_labels = None
depends_on = None

def upgrade() -> None:
    with op.batch_alter_table('meetings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('meeting_link', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('platform', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('auto_join', sa.Boolean(), nullable=False, server_default='1'))
        batch_op.add_column(sa.Column('consent_confirmed', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('consent_confirmed_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('bot_provider', sa.String(length=50), nullable=False, server_default='mock'))
        batch_op.add_column(sa.Column('bot_id', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('bot_status', sa.String(length=50), nullable=False, server_default='not_requested'))
        batch_op.add_column(sa.Column('bot_error', sa.Text(), nullable=True))
        batch_op.create_index(batch_op.f('ix_meetings_bot_id'), ['bot_id'], unique=False)

def downgrade() -> None:
    with op.batch_alter_table('meetings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_meetings_bot_id'))
        batch_op.drop_column('bot_error')
        batch_op.drop_column('bot_status')
        batch_op.drop_column('bot_id')
        batch_op.drop_column('bot_provider')
        batch_op.drop_column('consent_confirmed_at')
        batch_op.drop_column('consent_confirmed')
        batch_op.drop_column('auto_join')
        batch_op.drop_column('platform')
        batch_op.drop_column('meeting_link')

