"""add waiting room and moderation fields

Revision ID: 6f7a8b9c0d1e
Revises: 5e6f7a8b9c0d
Create Date: 2026-11-03 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '6f7a8b9c0d1e'
down_revision = '5e6f7a8b9c0d'
branch_labels = None
depends_on = None

def upgrade() -> None:
    with op.batch_alter_table('meetings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('waiting_room_enabled', sa.Boolean(), nullable=False, server_default='0'))

    with op.batch_alter_table('live_participants', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(length=30), nullable=False, server_default='admitted'))
        batch_op.add_column(sa.Column('is_muted', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('video_disabled', sa.Boolean(), nullable=False, server_default='0'))

def downgrade() -> None:
    with op.batch_alter_table('live_participants', schema=None) as batch_op:
        batch_op.drop_column('video_disabled')
        batch_op.drop_column('is_muted')
        batch_op.drop_column('status')

    with op.batch_alter_table('meetings', schema=None) as batch_op:
        batch_op.drop_column('waiting_room_enabled')

