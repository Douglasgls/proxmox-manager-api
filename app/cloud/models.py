from uuid import uuid4
from datetime import datetime

from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AgentSettings(Base):
    __tablename__ = "agent_settings"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    environment_token_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    jwt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    jwt_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    registered_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
