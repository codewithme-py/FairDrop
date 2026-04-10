from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ExternalProductRead(BaseModel):
    """
    Product representation for external partners.

    Attributes:
        id: Unique product identifier.
        name: Product name.
        price: Current product price.
        qty_available: Available stock quantity.
    """

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    price: Decimal
    qty_available: int


class ExternalOrderResponse(BaseModel):
    """
    Order status response for external partners.

    Attributes:
        id: Unique order identifier.
        status: Current order status string.
        updated_at: Timestamp of the last status update.
    """

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: str
    updated_at: datetime
