from uuid import uuid4
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Integer,
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

    # TODO: Talvez ter dois tipos de id, um uuid para o banco de dados e outro id numérico para o usuário, que seria o container_number. Isso facilitaria a identificação do container pelo usuário, sem precisar lidar com um uuid longo e complexo.

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

    password: Mapped[str]

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

    bridge: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    ip_mode: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    cidr: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    gateway: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True
    )

    firewall: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        default=False
    )

    mtu: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    vlan: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    mac_address: Mapped[str | None] = mapped_column(
        String(17),
        nullable=True
    )

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
