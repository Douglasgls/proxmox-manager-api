from uuid import uuid4
from datetime import datetime

from sqlalchemy import (
    Integer,
    String,
    ForeignKey,
    Text
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)

from .base import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=lambda: str(uuid4())
    )

    type: Mapped[str] = mapped_column(
        String(50)
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING"
    )

    progress: Mapped[int] = mapped_column(
        default=0
    )

    target_container: Mapped[str | None] = mapped_column(
        ForeignKey(
            "containers.id"
        )
    )

    container_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    current_step: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    current_component: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    output: Mapped[str | None] = mapped_column(
        Text
    )

    error: Mapped[str | None] = mapped_column(
        Text
    )

    started_at: Mapped[
        datetime | None
    ]

    finished_at: Mapped[
        datetime | None
    ]

    created_at: Mapped[
        datetime
    ] = mapped_column(
        default=datetime.now()
    )

    container = relationship(
        "Container",
        back_populates="jobs"
    )
