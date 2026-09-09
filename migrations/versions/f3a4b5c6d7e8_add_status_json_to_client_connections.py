"""add_status_json_to_client_connections

Revision ID: f3a4b5c6d7e8
Revises: e6f7a8b9c0d1
Create Date: 2026-09-09 18:54:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, Sequence[str], None] = 'e6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('client_connections') as batch_op:
        batch_op.add_column(sa.Column('status_json', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('client_connections') as batch_op:
        batch_op.drop_column('status_json')
