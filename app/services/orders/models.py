from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime, Integer, String

from app.core.database import Base

DECIMAL_PRECISION = 10
DECIMAL_SCALE = 2


class OrderStatus(StrEnum):
    PENDING = 'PENDING'
    PAID = 'PAID'
    SHIPPED = 'SHIPPED'
    CANCELLED = 'CANCELLED'
    FAILED = 'FAILED'
    COMPLETED = 'COMPLETED'
    EXPIRED = 'EXPIRED'


class Order(Base):
    __tablename__ = 'orders'

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey('users.id'), nullable=False, index=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING, index=True
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(DECIMAL_PRECISION, DECIMAL_SCALE), nullable=False
    )
    shipping_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list['OrderItem']] = relationship(
        'OrderItem', back_populates='order', cascade='all, delete-orphan'
    )

    __table_args__ = (
        CheckConstraint('total_amount >= 0', name='check_total_amount_non_negative'),
    )


class OrderItem(Base):
    __tablename__ = 'order_items'

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey('orders.id'), nullable=False, index=True
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey('products.id'), nullable=False, index=True
    )
    if TYPE_CHECKING:
        from app.services.inventory.models import Product
    product: Mapped['Product'] = relationship('Product')

    order: Mapped['Order'] = relationship('Order', back_populates='items')
    product_name: Mapped[str] = mapped_column(String(), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(
        Numeric(DECIMAL_PRECISION, DECIMAL_SCALE), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
