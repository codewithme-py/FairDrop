from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.services.inventory.models import ProductStatus
from app.services.orders.models import OrderStatus


class SellerProductRead(BaseModel):
    """
    Product representation for the owning seller.

    Includes moderation-related fields not shown to buyers.

    Attributes:
        id: Unique product identifier.
        name: Product name.
        description: Product description.
        price: Unit price.
        qty_available: Available stock.
        status: Current lifecycle status.
        moderation_comment: Optional comment from a moderator.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

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
    """
    A single line item within an order from the seller's perspective.

    Attributes:
        id: Unique item identifier.
        product_id: The sold product ID.
        product_name: Product name at time of purchase.
        quantity: Number of units sold.
        price: Unit price at time of purchase.
    """

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_id: UUID
    product_name: str
    quantity: int
    price: Decimal


class SellerOrderRead(BaseModel):
    """
    Order summary for a seller, showing only their line items.

    Attributes:
        id: Unique order identifier.
        status: Current order status.
        created_at: Order creation timestamp.
        shipping_address: Delivery address (hidden for pending/failed/cancelled orders).
        seller_items: Line items belonging to this seller.
    """

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: OrderStatus
    created_at: datetime
    shipping_address: str | None = None
    seller_items: list[SellerOrderItemRead] = Field(default_factory=list)


class SellerStats(BaseModel):
    """
    Statistics summary for a seller's products and orders.

    Attributes:
        total_products: Total number of products listed by the seller.
        active_products: Number of products in ACTIVE status.
        pending_moderation: Number of products awaiting moderation.
        rejected_products: Number of products rejected during moderation.
        pending_orders: Number of orders in PENDING status containing seller's products.
        paid_orders: Number of orders in PAID status containing seller's products.
    """

    total_products: int = 0
    active_products: int = 0
    pending_moderation: int = 0
    rejected_products: int = 0
    pending_orders: int = 0
    paid_orders: int = 0
