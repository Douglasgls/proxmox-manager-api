"""add_container_components_table

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-12 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'container_components',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('container_id', sa.String(length=36), nullable=False),
        sa.Column('component_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='PENDING'),
        sa.Column('installed_version', sa.String(length=50), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('installed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['component_id'], ['components.id'], ),
        sa.ForeignKeyConstraint(['container_id'], ['containers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('container_id', 'component_id', name='uq_container_component')
    )
    op.create_index(op.f('ix_container_components_component_id'), 'container_components', ['component_id'], unique=False)
    op.create_index(op.f('ix_container_components_container_id'), 'container_components', ['container_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_container_components_container_id'), table_name='container_components')
    op.drop_index(op.f('ix_container_components_component_id'), table_name='container_components')
    op.drop_table('container_components')
