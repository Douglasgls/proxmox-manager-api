from uuid import uuid4
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from .base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=lambda: str(uuid4())
    )

    username: Mapped[str] = mapped_column(
        String(80),
        unique=True
    )
    
    email: Mapped[str] = mapped_column(
        String(120),
        unique=True
    )

    password: Mapped[str]

    role: Mapped[str] = mapped_column(
        String(20),
        default="admin"
    )

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow
    )