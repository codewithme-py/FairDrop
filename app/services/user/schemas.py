from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from .models import UserRole, VerificationStatus


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


class VerificationRequestCreate(BaseModel):
    target_role: Literal[UserRole.USER_B2B, UserRole.SELLER_B2B, UserRole.SELLER]
    docs_url: dict[str, str] | None = None


class VerificationRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    target_role: UserRole
    status: VerificationStatus
    admin_feedback: str | None = None
    created_at: datetime
    updated_at: datetime
