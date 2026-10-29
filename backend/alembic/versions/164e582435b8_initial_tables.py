"""Initial tables

Revision ID: 164e582435b8
Revises: 
Create Date: 2026-10-28 14:52:33.932407

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '164e582435b8'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('job_title', sa.String(length=255), nullable=True),
        sa.Column('reset_token', sa.String(length=255), nullable=True),
        sa.Column('reset_token_expiry', sa.DateTime(), nullable=True),
        sa.Column('two_factor_enabled', sa.Boolean(), nullable=True),
        sa.Column('two_factor_secret', sa.String(length=64), nullable=True),
        sa.Column('backup_codes', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_id'), ['id'], unique=False)

    op.create_table('meetings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('audio_path', sa.String(length=500), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('participants', sa.JSON(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('color', sa.String(length=50), nullable=True),
        sa.Column('model_version', sa.String(length=50), nullable=True),
        sa.Column('primary_language', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('meetings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_meetings_id'), ['id'], unique=False)

    op.create_table('action_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('assignee', sa.String(length=100), nullable=True),
        sa.Column('deadline', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('priority', sa.String(length=50), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('needs_review', sa.Boolean(), nullable=True),
        sa.Column('model_version', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('action_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_action_items_id'), ['id'], unique=False)

    op.create_table('comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('comments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_comments_id'), ['id'], unique=False)

    op.create_table('decisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Integer(), nullable=False),
        sa.Column('decision_text', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('decisions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_decisions_id'), ['id'], unique=False)

    op.create_table('meeting_analytics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Integer(), nullable=False),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('talk_to_listen_ratio', sa.Float(), nullable=True),
        sa.Column('total_topics', sa.Integer(), nullable=True),
        sa.Column('speaking_time_distribution', sa.JSON(), nullable=True),
        sa.Column('topic_chapters', sa.JSON(), nullable=True),
        sa.Column('effectiveness_score', sa.Integer(), nullable=True),
        sa.Column('effectiveness_breakdown', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('meeting_id')
    )
    with op.batch_alter_table('meeting_analytics', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_meeting_analytics_id'), ['id'], unique=False)

    op.create_table('summaries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Integer(), nullable=False),
        sa.Column('overview', sa.Text(), nullable=False),
        sa.Column('key_takeaways', sa.JSON(), nullable=True),
        sa.Column('next_steps', sa.Text(), nullable=True),
        sa.Column('model_version', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('meeting_id')
    )
    with op.batch_alter_table('summaries', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_summaries_id'), ['id'], unique=False)

    op.create_table('transcripts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Integer(), nullable=False),
        sa.Column('speaker', sa.String(length=100), nullable=False),
        sa.Column('start_time', sa.Float(), nullable=True),
        sa.Column('end_time', sa.Float(), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('is_action_item', sa.Boolean(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('model_version', sa.String(length=50), nullable=True),
        sa.Column('language', sa.String(length=20), nullable=True),
        sa.Column('translated_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('transcripts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_transcripts_id'), ['id'], unique=False)

    op.create_table('human_corrections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action_item_id', sa.Integer(), nullable=True),
        sa.Column('original_text', sa.Text(), nullable=False),
        sa.Column('corrected_text', sa.Text(), nullable=False),
        sa.Column('original_assignee', sa.String(length=100), nullable=True),
        sa.Column('corrected_assignee', sa.String(length=100), nullable=True),
        sa.Column('original_deadline', sa.String(length=100), nullable=True),
        sa.Column('corrected_deadline', sa.String(length=100), nullable=True),
        sa.Column('correction_type', sa.String(length=50), nullable=True),
        sa.Column('model_version', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('human_corrections', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_human_corrections_id'), ['id'], unique=False)

    op.create_table('model_registry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('task_type', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('metrics', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('model_registry', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_model_registry_id'), ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('model_registry')
    op.drop_table('human_corrections')
    op.drop_table('transcripts')
    op.drop_table('summaries')
    op.drop_table('meeting_analytics')
    op.drop_table('decisions')
    op.drop_table('comments')
    op.drop_table('action_items')
    op.drop_table('meetings')
    op.drop_table('users')
