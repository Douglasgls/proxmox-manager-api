"""make_tailscale_node_container_id_nullable

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-08-19 18:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alter container_id and proxmox_container_id to nullable
    op.alter_column('tailscale_nodes', 'container_id', existing_type=sa.VARCHAR(), nullable=True)
    op.alter_column('tailscale_nodes', 'proxmox_container_id', existing_type=sa.INTEGER(), nullable=True)

    # Add node_type column
    op.add_column('tailscale_nodes', sa.Column('node_type', sa.String(length=20), server_default='container', nullable=False))


def downgrade() -> None:
    op.drop_column('tailscale_nodes', 'node_type')
    op.alter_column('tailscale_nodes', 'proxmox_container_id', existing_type=sa.INTEGER(), nullable=False)
    op.alter_column('tailscale_nodes', 'container_id', existing_type=sa.VARCHAR(), nullable=False)
