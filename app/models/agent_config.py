from uuid import uuid4
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AgentConfig(Base):
    __tablename__ = "agent_config"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4())
    )

    proxmox_host: Mapped[str] = mapped_column(String(255))
    proxmox_user: Mapped[str] = mapped_column(String(100))
    proxmox_token_name: Mapped[str] = mapped_column(String(100))
    proxmox_token_value: Mapped[str] = mapped_column(String(500))  # Criptografado
    proxmox_node: Mapped[str] = mapped_column(String(100))

    default_storage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_template: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now,
        onupdate=datetime.now
    )
