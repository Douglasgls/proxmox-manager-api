"""create_client_connections_table

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-08-19 18:31:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'client_connections',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('cloud_connection_id', sa.String(length=36), nullable=True),
        sa.Column('headscale_node_id', sa.String(length=100), nullable=True),
        sa.Column('container_id', sa.String(), nullable=True),
        sa.Column('hostname', sa.String(length=100), nullable=True),
        sa.Column('tailscale_ip', sa.String(length=50), nullable=True),
        sa.Column('online', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='ACTIVE'),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['container_id'], ['containers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index(op.f('ix_client_connections_cloud_connection_id'), 'client_connections', ['cloud_connection_id'], unique=False)
    op.create_index(op.f('ix_client_connections_container_id'), 'client_connections', ['container_id'], unique=False)
    op.create_index(op.f('ix_client_connections_headscale_node_id'), 'client_connections', ['headscale_node_id'], unique=False)
    op.create_index(op.f('ix_client_connections_tailscale_ip'), 'client_connections', ['tailscale_ip'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_client_connections_tailscale_ip'), table_name='client_connections')
    op.drop_index(op.f('ix_client_connections_headscale_node_id'), table_name='client_connections')
    op.drop_index(op.f('ix_client_connections_container_id'), table_name='client_connections')
    op.drop_index(op.f('ix_client_connections_cloud_connection_id'), table_name='client_connections')
    op.drop_table('client_connections')
