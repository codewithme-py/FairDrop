from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OrderCreate(BaseModel):
    reservation_id: UUID
    shipping_address: str | None = None


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_id: UUID
    product_name: str
    quantity: int
    price: Decimal


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    status: str
    total_amount: Decimal
    shipping_address: str | None = None
    created_at: datetime
    items: list[OrderItemResponse]
