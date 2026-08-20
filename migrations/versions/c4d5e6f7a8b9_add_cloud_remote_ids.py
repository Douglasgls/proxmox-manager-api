"""add_cloud_remote_ids

Revision ID: c4d5e6f7a8b9
Revises: 66d84daaed9b
Create Date: 2026-08-19 17:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = '66d84daaed9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add cloud_environment_id to agent_settings
    op.add_column(
        'agent_settings',
        sa.Column('cloud_environment_id', sa.String(length=36), nullable=True)
    )

    # Add cloud_container_id to containers
    op.add_column(
        'containers',
        sa.Column('cloud_container_id', sa.String(length=36), nullable=True)
    )
    op.create_index(
        op.f('ix_containers_cloud_container_id'),
        'containers',
        ['cloud_container_id'],
        unique=False
    )

    # Add headscale_node_id to tailscale_nodes
    op.add_column(
        'tailscale_nodes',
        sa.Column('headscale_node_id', sa.String(length=100), nullable=True)
    )
    op.create_index(
        op.f('ix_tailscale_nodes_headscale_node_id'),
        'tailscale_nodes',
        ['headscale_node_id'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_tailscale_nodes_headscale_node_id'), table_name='tailscale_nodes')
    op.drop_column('tailscale_nodes', 'headscale_node_id')

    op.drop_index(op.f('ix_containers_cloud_container_id'), table_name='containers')
    op.drop_column('containers', 'cloud_container_id')

    op.drop_column('agent_settings', 'cloud_environment_id')
