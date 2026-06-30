from uuid import uuid4
from datetime import datetime

from sqlalchemy import (
    String,
    ForeignKey
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)

from .base import Base


class Container(Base):
    __tablename__ = "containers"

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=lambda: str(uuid4())
    )

    container_number: Mapped[int] = mapped_column(
        unique=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True
    )

    description: Mapped[str | None]

    status: Mapped[str] = mapped_column(
        String(20),
        default="stopped"
    )

    cpu: Mapped[int] = mapped_column(
        default=1
    )

    memory_mb: Mapped[int] = mapped_column(
        default=512
    )

    disk_gb: Mapped[int] = mapped_column(
        default=2
    )

    ip_address: Mapped[str | None]

    image_name: Mapped[str | None]

    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id")
    )

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now(),
        onupdate=datetime.now()
    )

    user = relationship(
        "User"
    )

    jobs = relationship(
        "Job",
        back_populates="container"
    )