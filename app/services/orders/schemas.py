from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OrderCreate(BaseModel):
    """
    Payload for creating a new order from a reservation.

    Attributes:
        reservation_id: ID of the reservation to convert into an order.
        shipping_address: Optional delivery address.
    """

    reservation_id: UUID
    shipping_address: str | None = None


class OrderItemResponse(BaseModel):
    """
    A single line item within an order response.

    Attributes:
        id: Unique item identifier.
        product_id: Purchased product ID.
        product_name: Product name snapshot at time of purchase.
        quantity: Number of units.
        price: Unit price at time of purchase.
    """

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_id: UUID
    product_name: str
    quantity: int
    price: Decimal


class OrderResponse(BaseModel):
    """
    Full order response returned to clients.

    Attributes:
        id: Unique order identifier.
        user_id: ID of the ordering user.
        status: Current order status.
        total_amount: Total order value.
        shipping_address: Delivery address.
        created_at: Creation timestamp.
        items: Line items in the order.
    """

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    status: str
    total_amount: Decimal
    shipping_address: str | None = None
    created_at: datetime
    items: list[OrderItemResponse]
