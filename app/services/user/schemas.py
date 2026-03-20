from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from .models import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    role: UserRole


class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class APIKeyCreate(BaseModel):
    name: str


class APIKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    expires_at: datetime | None = None
    last_used_at: datetime | None = None


class APIKeyWithSecret(APIKeyRead):
    raw_key: str
