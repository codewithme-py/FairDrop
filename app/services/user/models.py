from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import JSON, ForeignKey
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import Boolean, DateTime, String

from app.core.database import Base

EMAIL_MAX_LENGTH = 255


class UserRole(StrEnum):
    ADMIN = 'ADMIN'
    MODERATOR = 'MODERATOR'
    USER = 'USER'
    USER_B2B = 'USER_B2B'
    SELLER = 'SELLER'
    SELLER_B2B = 'SELLER_B2B'


class VerificationStatus(StrEnum):
    PENDING = 'PENDING'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'


class User(Base):
    __tablename__ = 'users'
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(
        String(EMAIL_MAX_LENGTH), unique=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), default=UserRole.USER)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    refresh_tokens: Mapped[list['RefreshToken']] = relationship(back_populates='user')
    api_keys_b2b_partners: Mapped[list['APIKeyB2BPartner']] = relationship(
        back_populates='user'
    )
    verification_requests: Mapped[list['VerificationRequest']] = relationship(
        back_populates='user'
    )


class RefreshToken(Base):
    __tablename__ = 'refresh_tokens'
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), nullable=False
    )
    token: Mapped[str] = mapped_column(
        String(), unique=True, nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    user: Mapped[User] = relationship(back_populates='refresh_tokens')


class APIKeyB2BPartner(Base):
    __tablename__ = 'api_keys_b2b_partners'
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    hashed_key: Mapped[str] = mapped_column(String(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    user: Mapped[User] = relationship(back_populates='api_keys_b2b_partners')


class VerificationRequest(Base):
    __tablename__ = 'verification_requests'
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True
    )
    target_role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), nullable=False)
    status: Mapped[VerificationStatus] = mapped_column(
        SQLEnum(VerificationStatus), default=VerificationStatus.PENDING
    )
    docs_url: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    admin_feedback: Mapped[str | None] = mapped_column(String(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    user: Mapped[User] = relationship(back_populates='verification_requests')
