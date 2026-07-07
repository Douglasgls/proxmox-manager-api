"""add job progress fields

Revision ID: 7b4f7c1a9d2e
Revises: 2254631a549d
Create Date: 2026-07-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7b4f7c1a9d2e"
down_revision: Union[str, Sequence[str], None] = "2254631a549d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "container_id",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.add_column(
        "jobs",
        sa.Column(
            "current_step",
            sa.String(
                length=100
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "jobs",
        sa.Column(
            "current_component",
            sa.String(
                length=100
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "jobs",
        "current_component",
    )
    op.drop_column(
        "jobs",
        "current_step",
    )
    op.drop_column(
        "jobs",
        "container_id",
    )
