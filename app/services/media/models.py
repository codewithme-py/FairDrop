from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime, String

from app.core.database import Base


class ImageStatus(StrEnum):
    PENDING = 'pending'
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    FAILED = 'failed'


class ProductImage(Base):
    __tablename__ = 'product_images'
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(ForeignKey('products.id'))
    file_path: Mapped[str] = mapped_column(String(), nullable=False)
    status: Mapped[str] = mapped_column(
        String(), nullable=False, default=ImageStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    if TYPE_CHECKING:
        from app.services.inventory.models import Product
    product: Mapped['Product'] = relationship(back_populates='images')
