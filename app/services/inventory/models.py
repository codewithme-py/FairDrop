from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime, Integer, String, Text

from app.core.database import Base

DECIMAL_PRECISION = 10
DECIMAL_SCALE = 2


class Product(Base):
    __tablename__ = 'products'

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    price: Mapped[Decimal] = mapped_column(
        Numeric(DECIMAL_PRECISION, DECIMAL_SCALE),
        nullable=False,
        default=Decimal('0.10'),
    )
    qty_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint('qty_available >= 0', name='check_qty_non_negative'),
        CheckConstraint('price >= 0.10', name='check_price_non_negative'),
    )


class Reservation(Base):
    __tablename__ = 'reservations'

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    qty_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey('products.id'), nullable=False)
    status: Mapped[str] = mapped_column(String(), nullable=False, default='pending')
    idempotency_key: Mapped[str] = mapped_column(String(), nullable=False, unique=True)
    order_id: Mapped[UUID | None] = mapped_column(
        ForeignKey('orders.id'), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
