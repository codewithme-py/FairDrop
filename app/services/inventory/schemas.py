from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.services.inventory.models import ProductStatus


class ProductCreate(BaseModel):
    name: str
    description: str | None = None
    price: Decimal = Field(gt=0, description='Price must be greater than 0')
    qty_available: int = Field(
        ge=0, description='Quantity must be greater than or equal to 0'
    )


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: Decimal | None = Field(
        default=None, gt=0, description='Price must be greater than 0'
    )
    qty_available: int | None = Field(
        default=None, ge=0, description='Quantity must be greater than or equal to 0'
    )


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None = None
    price: Decimal
    qty_available: int
    status: ProductStatus
    created_at: datetime
    updated_at: datetime


class ReservationCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0, description='Quantity must be greater than 0')


class ReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_id: UUID
    user_id: UUID
    quantity: int = Field(validation_alias='qty_reserved')
    status: str
    expires_at: datetime
