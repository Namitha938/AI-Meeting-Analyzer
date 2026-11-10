"""Add live meeting fields, participants, and chat tables

Revision ID: 4d5e6f7a8b9c
Revises: 3c4d5e6f7a8b
Create Date: 2026-11-03 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '4d5e6f7a8b9c'
down_revision: Union[str, Sequence[str], None] = '3c4d5e6f7a8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns to meetings table
    with op.batch_alter_table('meetings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source', sa.String(length=50), server_default='upload', nullable=False))
        batch_op.add_column(sa.Column('is_live', sa.Boolean(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('room_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('meeting_code', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('passcode_hash', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('live_status', sa.String(length=50), server_default='scheduled', nullable=False))
        batch_op.add_column(sa.Column('host_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('started_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('ended_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('record_mode', sa.String(length=50), server_default='audio_video', nullable=False))
        batch_op.add_column(sa.Column('locked', sa.Boolean(), server_default='0', nullable=False))
        batch_op.create_foreign_key('fk_meetings_host_id', 'users', ['host_id'], ['id'])
        batch_op.create_index(batch_op.f('ix_meetings_meeting_code'), ['meeting_code'], unique=True)

    # Create live_participants table
    op.create_table(
        'live_participants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('display_name', sa.String(length=150), nullable=False),
        sa.Column('role', sa.String(length=20), server_default='participant', nullable=False),
        sa.Column('joined_at', sa.DateTime(), nullable=False),
        sa.Column('left_at', sa.DateTime(), nullable=True),
        sa.Column('consent_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('live_participants', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_live_participants_meeting_id'), ['meeting_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_live_participants_user_id'), ['user_id'], unique=False)

    # Create meeting_chats table
    op.create_table(
        'meeting_chats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Integer(), nullable=False),
        sa.Column('sender_id', sa.Integer(), nullable=True),
        sa.Column('sender_name', sa.String(length=100), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_private', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('recipient_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('meeting_chats', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_meeting_chats_meeting_id'), ['meeting_id'], unique=False)


def downgrade() -> None:
    op.drop_table('meeting_chats')
    op.drop_table('live_participants')
    with op.batch_alter_table('meetings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_meetings_meeting_code'))
        batch_op.drop_constraint('fk_meetings_host_id', type_='foreignkey')
        batch_op.drop_column('locked')
        batch_op.drop_column('record_mode')
        batch_op.drop_column('ended_at')
        batch_op.drop_column('started_at')
        batch_op.drop_column('host_id')
        batch_op.drop_column('live_status')
        batch_op.drop_column('passcode_hash')
        batch_op.drop_column('meeting_code')
        batch_op.drop_column('room_name')
        batch_op.drop_column('is_live')
        batch_op.drop_column('source')
