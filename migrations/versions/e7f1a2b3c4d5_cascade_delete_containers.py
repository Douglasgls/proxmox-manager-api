"""cascade delete containers

Revision ID: e7f1a2b3c4d5
Revises: f2a7d5c9e1b3
Create Date: 2026-07-21 12:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "f2a7d5c9e1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "jobs_target_container_fkey",
        "jobs",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "jobs_target_container_fkey",
        "jobs",
        "containers",
        ["target_container"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "container_actions_container_id_fkey",
        "container_actions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "container_actions_container_id_fkey",
        "container_actions",
        "containers",
        ["container_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "container_actions_container_id_fkey",
        "container_actions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "container_actions_container_id_fkey",
        "container_actions",
        "containers",
        ["container_id"],
        ["id"],
    )

    op.drop_constraint(
        "jobs_target_container_fkey",
        "jobs",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "jobs_target_container_fkey",
        "jobs",
        "containers",
        ["target_container"],
        ["id"],
    )
