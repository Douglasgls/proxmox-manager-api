"""create access_tokens table

Revision ID: dd46f67d168c
Revises: 88af6938d577
Create Date: 2026-07-16 22:06:22.628509

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd46f67d168c'
down_revision: Union[str, Sequence[str], None] = '88af6938d577'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'access_tokens',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('container_id', sa.String(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['container_id'], ['containers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_access_tokens_active'), 'access_tokens', ['active'], unique=False)
    op.create_index(op.f('ix_access_tokens_container_id'), 'access_tokens', ['container_id'], unique=False)
    op.create_index(op.f('ix_access_tokens_token_hash'), 'access_tokens', ['token_hash'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_access_tokens_token_hash'), table_name='access_tokens')
    op.drop_index(op.f('ix_access_tokens_container_id'), table_name='access_tokens')
    op.drop_index(op.f('ix_access_tokens_active'), table_name='access_tokens')
    op.drop_table('access_tokens')
