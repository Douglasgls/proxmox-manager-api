from datetime import datetime
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Any

from app.models.base import Base


class TailscaleNode(Base):
    __tablename__ = "tailscale_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    container_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("containers.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    
    proxmox_container_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    installed: Mapped[bool] = mapped_column(Boolean, default=False)
    service_running: Mapped[bool] = mapped_column(Boolean, default=False)
    
    version: Mapped[str | None] = mapped_column(String, nullable=True)
    machine_id: Mapped[str | None] = mapped_column(String, nullable=True)
    node_key: Mapped[str | None] = mapped_column(String, nullable=True)
    tailscale_ip: Mapped[str | None] = mapped_column(String, nullable=True)
    
    status_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    last_sync: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    container = relationship("Container", backref="tailscale_node")

    @property
    def online(self) -> bool:
        """Indica se o node está online na rede Tailscale."""
        if self.status_json and isinstance(self.status_json, dict):
            return self.status_json.get("Self", {}).get("Online", False)
        return False

