"""Add meeting effectiveness_score and effectiveness_pillars

Revision ID: 3c4d5e6f7a8b
Revises: 2a3b4c5d6e7f
Create Date: 2026-11-02 21:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '3c4d5e6f7a8b'
down_revision: Union[str, Sequence[str], None] = '2a3b4c5d6e7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('meetings', sa.Column('effectiveness_score', sa.Integer(), nullable=True))
    op.add_column('meetings', sa.Column('effectiveness_pillars', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('meetings', 'effectiveness_pillars')
    op.drop_column('meetings', 'effectiveness_score')

