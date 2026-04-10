from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BuyerStats(BaseModel):
    """
    Statistics summary for a buyer's order history.

    Attributes:
        total_orders: Total number of orders placed by the buyer.
        pending_orders: Number of orders in PENDING status.
        paid_orders: Number of orders in PAID status.
        shipped_orders: Number of orders in SHIPPED status.
    """

    total_orders: int
    pending_orders: int
    paid_orders: int
    shipped_orders: int


class BuyerOrderItemRead(BaseModel):
    """
    A single line item within a buyer's order.

    Attributes:
        id: Unique identifier for the order item.
        product_id: Identifier of the purchased product.
        product_name: Name of the product at time of purchase.
        quantity: Number of units purchased.
        price: Unit price at time of purchase.
    """

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_id: UUID
    product_name: str
    quantity: int
    price: Decimal


class BuyerOrderRead(BaseModel):
    """
    Order summary returned to a buyer.

    Attributes:
        id: Unique identifier for the order.
        status: Current order status.
        total_amount: Total order value.
        shipping_address: Destination address for delivery.
        created_at: Timestamp when the order was created.
        items: Line items belonging to the order.
    """

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: str
    total_amount: Decimal
    shipping_address: str | None = None
    created_at: datetime
    items: list[BuyerOrderItemRead]
