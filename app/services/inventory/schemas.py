from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReservationCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0, description='Quantity must be greater than 0')


class ReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_id: UUID
    user_id: UUID
    quantity: int
    status: str
    expires_at: datetime
