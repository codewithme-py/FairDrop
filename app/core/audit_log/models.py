from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import JSON, DateTime, String

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = 'audit_logs'

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    target_type: Mapped[str] = mapped_column(String(), nullable=False, index=True)
    target_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    actor_id: Mapped[UUID] = mapped_column(
        ForeignKey('users.id'), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(), nullable=False, index=True)
    changes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    remote_ip: Mapped[str | None] = mapped_column(String(45), index=True)
    request_id: Mapped[str | None] = mapped_column(index=True)
