"""add container network configuration

Revision ID: 9c8b1e2a4d31
Revises: d62f6d2b15bb
Create Date: 2026-07-01 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c8b1e2a4d31'
down_revision: Union[str, Sequence[str], None] = 'd62f6d2b15bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'containers',
        sa.Column('bridge', sa.String(length=50), nullable=True),
    )
    op.add_column(
        'containers',
        sa.Column('ip_mode', sa.String(length=20), nullable=True),
    )
    op.add_column(
        'containers',
        sa.Column('cidr', sa.Integer(), nullable=True),
    )
    op.add_column(
        'containers',
        sa.Column('gateway', sa.String(length=45), nullable=True),
    )
    op.add_column(
        'containers',
        sa.Column('firewall', sa.Boolean(), nullable=True),
    )
    op.add_column(
        'containers',
        sa.Column('mtu', sa.Integer(), nullable=True),
    )
    op.add_column(
        'containers',
        sa.Column('vlan', sa.Integer(), nullable=True),
    )
    op.add_column(
        'containers',
        sa.Column('mac_address', sa.String(length=17), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('containers', 'mac_address')
    op.drop_column('containers', 'vlan')
    op.drop_column('containers', 'mtu')
    op.drop_column('containers', 'firewall')
    op.drop_column('containers', 'gateway')
    op.drop_column('containers', 'cidr')
    op.drop_column('containers', 'ip_mode')
    op.drop_column('containers', 'bridge')
