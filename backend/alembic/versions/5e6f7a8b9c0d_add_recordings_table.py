"""add recordings table

Revision ID: 5e6f7a8b9c0d
Revises: 4d5e6f7a8b9c
Create Date: 2026-11-03 19:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '5e6f7a8b9c0d'
down_revision = '4d5e6f7a8b9c'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'recordings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=50), nullable=False, server_default='composite_video'),
        sa.Column('participant_id', sa.String(length=100), nullable=True),
        sa.Column('storage_key', sa.String(length=500), nullable=True),
        sa.Column('duration', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('size_bytes', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='recording'),
        sa.Column('egress_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recordings_id'), 'recordings', ['id'], unique=False)
    op.create_index(op.f('ix_recordings_meeting_id'), 'recordings', ['meeting_id'], unique=False)
    op.create_index(op.f('ix_recordings_egress_id'), 'recordings', ['egress_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_recordings_egress_id'), table_name='recordings')
    op.drop_index(op.f('ix_recordings_meeting_id'), table_name='recordings')
    op.drop_index(op.f('ix_recordings_id'), table_name='recordings')
    op.drop_table('recordings')

