from uuid import uuid4
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ClientConnection(Base):
    __tablename__ = "client_connections"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    cloud_connection_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    headscale_node_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    container_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("containers.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    hostname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tailscale_ip: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    online: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    container = relationship("Container", back_populates="client_connections", passive_deletes=True)
