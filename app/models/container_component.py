from enum import Enum
from uuid import uuid4
from datetime import datetime

from sqlalchemy import String, Text, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ContainerComponentStatus(str, Enum):
    PENDING = "PENDING"
    INSTALLING = "INSTALLING"
    INSTALLED = "INSTALLED"
    FAILED = "FAILED"


class ContainerComponent(Base):
    """Modelo ORM representando a relação entre um Container e um Componente instalado/solicitado."""

    __tablename__ = "container_components"

    __table_args__ = (
        UniqueConstraint("container_id", "component_id", name="uq_container_component"),
    )

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=lambda: str(uuid4())
    )

    container_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("containers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    component_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("components.id"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default=ContainerComponentStatus.PENDING.value,
        nullable=False,
    )

    installed_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
    )

    installed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    container = relationship(
        "Container",
        back_populates="container_components",
    )

    component = relationship(
        "Component",
    )

    def __repr__(self):
        return f"<ContainerComponent container_id={self.container_id} component_id={self.component_id} status={self.status}>"
