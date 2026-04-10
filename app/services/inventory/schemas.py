from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.services.inventory.models import ProductStatus


class ProductCreate(BaseModel):
    """
    Payload for creating a new product.

    Attributes:
        name: Product name.
        description: Optional product description.
        price: Unit price, must be greater than 0.
        qty_available: Initial stock quantity, must be >= 0.
    """

    name: str
    description: str | None = None
    price: Decimal = Field(gt=0, description='Price must be greater than 0')
    qty_available: int = Field(
        ge=0, description='Quantity must be greater than or equal to 0'
    )


class ProductUpdate(BaseModel):
    """
    Payload for updating an existing product.

    All fields are optional; only provided fields will be updated.

    Attributes:
        name: New product name.
        description: New product description.
        price: New unit price, must be greater than 0 if provided.
        qty_available: New stock quantity, must be >= 0 if provided.
    """

    name: str | None = None
    description: str | None = None
    price: Decimal | None = Field(
        default=None, gt=0, description='Price must be greater than 0'
    )
    qty_available: int | None = Field(
        default=None, ge=0, description='Quantity must be greater than or equal to 0'
    )


class ProductRead(BaseModel):
    """
    Full product representation returned to clients.

    Attributes:
        id: Unique product identifier.
        name: Product name.
        description: Product description.
        price: Unit price.
        qty_available: Available stock.
        status: Current lifecycle status.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        image_urls: List of presigned URLs for product images.
    """

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None = None
    price: Decimal
    qty_available: int
    status: ProductStatus
    created_at: datetime
    updated_at: datetime
    image_urls: list[str] = []


class ReservationCreate(BaseModel):
    """
    Payload for reserving stock for a product.

    Attributes:
        product_id: ID of the product to reserve.
        quantity: Number of units to reserve, must be > 0.
    """

    product_id: UUID
    quantity: int = Field(gt=0, description='Quantity must be greater than 0')


class ReservationResponse(BaseModel):
    """
    Response body for a stock reservation.

    Attributes:
        id: Reservation identifier.
        product_id: Reserved product ID.
        user_id: Reserving user ID.
        quantity: Number of units reserved.
        status: Current reservation status.
        expires_at: Expiration timestamp.
    """

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_id: UUID
    user_id: UUID
    quantity: int = Field(validation_alias='qty_reserved')
    status: str
    expires_at: datetime
