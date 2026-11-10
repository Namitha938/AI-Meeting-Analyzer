"""action item suggestion status and seek timestamps

Revision ID: 8b9c0d1e2f3a
Revises: 7a8b9c0d1e2f
Create Date: 2026-11-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '8b9c0d1e2f3a'
down_revision = '7a8b9c0d1e2f'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if 'action_items' in inspector.get_table_names():
        existing_cols = {c['name'] for c in inspector.get_columns('action_items')}
        if 'status' not in existing_cols:
            op.add_column('action_items', sa.Column('status', sa.String(50), nullable=False, server_default='confirmed'))
        if 'start_time_sec' not in existing_cols:
            op.add_column('action_items', sa.Column('start_time_sec', sa.Float(), nullable=True))
        if 'source_segment_id' not in existing_cols:
            op.add_column('action_items', sa.Column('source_segment_id', sa.Integer(), nullable=True))

    if 'decisions' in inspector.get_table_names():
        existing_dec_cols = {c['name'] for c in inspector.get_columns('decisions')}
        if 'start_time_sec' not in existing_dec_cols:
            op.add_column('decisions', sa.Column('start_time_sec', sa.Float(), nullable=True))
        if 'source_segment_id' not in existing_dec_cols:
            op.add_column('decisions', sa.Column('source_segment_id', sa.Integer(), nullable=True))


def downgrade():
    pass

