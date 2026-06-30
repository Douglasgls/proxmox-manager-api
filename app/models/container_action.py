from uuid import uuid4
from datetime import datetime

from sqlalchemy import (
    ForeignKey,
    Integer,
    Text
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column
)

from .base import Base


class ContainerAction(Base):
    __tablename__ = "container_actions"

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=lambda: str(uuid4())
    )

    container_id: Mapped[str] = mapped_column(
        ForeignKey(
            "containers.id"
        )
    )

    action: Mapped[str]

    status: Mapped[str]

    duration_ms: Mapped[
        int | None
    ] = mapped_column(
        Integer
    )

    error: Mapped[
        str | None
    ] = mapped_column(
        Text
    )

    executed_at: Mapped[
        datetime
    ] = mapped_column(
        default=datetime.now()
    )