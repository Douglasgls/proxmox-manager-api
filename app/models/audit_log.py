from uuid import uuid4
from datetime import datetime

from sqlalchemy import (
    JSON
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column
)

from .base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=lambda: str(uuid4())
    )

    entity_type: Mapped[str]

    entity_id: Mapped[
        str | None
    ]

    action: Mapped[str]

    details: Mapped[
        dict | None
    ] = mapped_column(
        JSON
    )

    created_at: Mapped[
        datetime
    ] = mapped_column(
        default=datetime.now()
    )