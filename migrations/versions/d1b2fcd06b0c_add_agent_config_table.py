"""add agent_config table

Revision ID: d1b2fcd06b0c
Revises: f3a4b5c6d7e8
Create Date: 2026-09-10 15:08:59.321821

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1b2fcd06b0c'
down_revision: Union[str, Sequence[str], None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('agent_config',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('proxmox_host', sa.String(length=255), nullable=False),
        sa.Column('proxmox_user', sa.String(length=100), nullable=False),
        sa.Column('proxmox_token_name', sa.String(length=100), nullable=False),
        sa.Column('proxmox_token_value', sa.String(length=500), nullable=False),
        sa.Column('proxmox_node', sa.String(length=100), nullable=False),
        sa.Column('default_storage', sa.String(length=100), nullable=True),
        sa.Column('default_template', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('agent_config')
