"""remove agent connection timestamps

Revision ID: f2a7d5c9e1b3
Revises: b9e4c2d1f8a7
Create Date: 2026-07-18 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f2a7d5c9e1b3"
down_revision: Union[str, Sequence[str], None] = "b9e4c2d1f8a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("agent_settings") as batch_op:
        batch_op.drop_column("last_connection")
        batch_op.drop_column("last_authentication")


def downgrade() -> None:
    with op.batch_alter_table("agent_settings") as batch_op:
        batch_op.add_column(sa.Column("last_authentication", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("last_connection", sa.DateTime(), nullable=True))
