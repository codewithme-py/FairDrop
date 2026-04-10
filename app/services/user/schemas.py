from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from .models import UserRole, VerificationStatus


class UserCreate(BaseModel):
    """
    Payload for registering a new user.

    Attributes:
        email: User email address for login.
        password: Plain-text password (will be hashed server-side).
    """

    email: EmailStr
    password: str


class UserRead(BaseModel):
    """
    Public user profile returned after registration or profile retrieval.

    Attributes:
        id: Unique user identifier.
        email: User email address.
        role: Current user role.
    """

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    role: UserRole


class Token(BaseModel):
    """
    Authentication token response.

    Attributes:
        access_token: JWT access token for API requests.
        token_type: Token type (always 'bearer').
        refresh_token: Refresh token for obtaining new access tokens.
    """

    access_token: str
    token_type: str
    refresh_token: str | None = None


class RefreshTokenRequest(BaseModel):
    """
    Request body for token refresh.

    Attributes:
        refresh_token: Valid refresh token to exchange.
    """

    refresh_token: str


class APIKeyCreate(BaseModel):
    """
    Payload for creating a B2B API key.

    Attributes:
        name: Human-readable name for the key.
    """

    name: str


class APIKeyRead(BaseModel):
    """
    B2B API key metadata (excluding the secret).

    Attributes:
        id: Unique key identifier.
        name: Human-readable key name.
        key_prefix: First 12 characters for identification.
        is_active: Whether the key is currently active.
        created_at: Creation timestamp.
        expires_at: Optional expiration timestamp.
        last_used_at: Timestamp of last use.
    """

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    expires_at: datetime | None = None
    last_used_at: datetime | None = None


class APIKeyWithSecret(APIKeyRead):
    """
    API key response including the raw secret (returned only once).

    Attributes:
        raw_key: The full secret key string. Must be stored securely by the client.
    """

    raw_key: str


class VerificationRequestCreate(BaseModel):
    """
    Payload for submitting a role upgrade request.

    Attributes:
        target_role: The role being requested (USER_B2B, SELLER_B2B, or SELLER).
        docs_url: Optional dictionary of verification document URLs.
    """

    target_role: Literal[UserRole.USER_B2B, UserRole.SELLER_B2B, UserRole.SELLER]
    docs_url: dict[str, str] | None = None


class VerificationRequestRead(BaseModel):
    """
    Verification request details returned to the requesting user.

    Attributes:
        id: Unique request identifier.
        target_role: The role that was requested.
        status: Current verification status.
        admin_feedback: Optional feedback from admin review.
        created_at: Request creation timestamp.
        updated_at: Last update timestamp.
    """

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    target_role: UserRole
    status: VerificationStatus
    admin_feedback: str | None = None
    created_at: datetime
    updated_at: datetime
