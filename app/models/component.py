from enum import Enum
from uuid import uuid4
from datetime import datetime

from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ComponentCategory(str, Enum):
    NATIVE = "native"
    DOCKER_APPS = "docker_apps"


class Component(Base):
    """Modelo ORM para o catálogo persistido de componentes disponíveis no Agent."""

    __tablename__ = "components"

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=lambda: str(uuid4())
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )

    category: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="1.0.0",
    )

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
    )

    def __repr__(self):
        return f"<Component slug={self.slug} name={self.name} category={self.category}>"
