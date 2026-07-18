"""remove obsolete agent settings fields

Revision ID: b9e4c2d1f8a7
Revises: 66da1919684f
Create Date: 2026-07-18 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b9e4c2d1f8a7"
down_revision: Union[str, Sequence[str], None] = "66da1919684f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("agent_settings") as batch_op:
        batch_op.drop_column("agent_name")
        batch_op.drop_column("cloud_url")
        batch_op.drop_column("environment_id")


def downgrade() -> None:
    with op.batch_alter_table("agent_settings") as batch_op:
        batch_op.add_column(sa.Column("environment_id", sa.String(255), nullable=True))
        batch_op.add_column(
            sa.Column("cloud_url", sa.String(512), nullable=False, server_default="")
        )
        batch_op.add_column(sa.Column("agent_name", sa.String(255), nullable=True))
