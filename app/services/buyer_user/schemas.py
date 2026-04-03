from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BuyerStats(BaseModel):
    total_orders: int
    pending_orders: int
    paid_orders: int
    shipped_orders: int


class BuyerOrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_id: UUID
    product_name: str
    quantity: int
    price: Decimal


class BuyerOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: str
    total_amount: Decimal
    shipping_address: str | None = None
    created_at: datetime
    items: list[BuyerOrderItemRead]
