from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.services.inventory.models import ProductStatus
from app.services.orders.models import OrderStatus


class SellerProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None = None
    price: Decimal
    qty_available: int
    status: ProductStatus
    moderation_comment: str | None = None
    created_at: datetime
    updated_at: datetime


class SellerOrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_id: UUID
    product_name: str
    quantity: int
    price: Decimal


class SellerOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: OrderStatus
    created_at: datetime
    shipping_address: str | None = None
    seller_items: list[SellerOrderItemRead] = Field(default_factory=list)


class SellerStats(BaseModel):
    total_products: int = 0
    active_products: int = 0
    pending_moderation: int = 0
    rejected_products: int = 0
    pending_orders: int = 0
    paid_orders: int = 0
