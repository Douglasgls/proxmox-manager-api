"""secure user credentials for stateless authentication

Revision ID: c3d1a9e8f6b2
Revises: 7b4f7c1a9d2e
Create Date: 2026-07-11 00:00:00.000000
"""

from typing import Sequence, Union

import bcrypt
import sqlalchemy as sa
from alembic import op


revision: str = "c3d1a9e8f6b2"
down_revision: Union[str, Sequence[str], None] = "7b4f7c1a9d2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(), nullable=True),
    )

    legacy_password_hash = bcrypt.hashpw(
        b"password-reset-required",
        bcrypt.gensalt(),
    ).decode()
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE users SET password_hash = :password_hash "
            "WHERE password_hash IS NULL"
        ),
        {"password_hash": legacy_password_hash},
    )

    op.alter_column("users", "password_hash", nullable=False)
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=True,
        ),
    )
    connection.execute(
        sa.text(
            "UPDATE users SET updated_at = created_at WHERE updated_at IS NULL"
        )
    )
    op.alter_column("users", "updated_at", nullable=False)
    op.alter_column("users", "is_active", server_default=None)
    op.drop_column("users", "password")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password", sa.String(), nullable=True),
    )
    op.drop_column("users", "updated_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "password_hash")
