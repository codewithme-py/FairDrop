import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.exceptions import (
    CredentialsError,
    NotFoundError,
    PermissionDeniedError,
    UserAlreadyExists,
    VerificationRequestAlreadyExists,
)
from app.core.hashing import get_password_hash
from app.services.user.models import (
    APIKeyB2BPartner,
    RefreshToken,
    User,
    UserRole,
    VerificationStatus,
)
from app.services.user.schemas import UserCreate
from app.services.user.service import UserService


@pytest.fixture
async def sample_user(db_session: Any) -> Any:
    """Create a sample user for user service coverage tests."""
    user = User(
        id=uuid4(),
        email=f'usr_{uuid4().hex}@mail.com',
        password_hash=await get_password_hash('password123'),
        role=UserRole.USER,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_create_user_success(db_session: Any) -> None:
    """
    Verify UserService.create_user creates a new user and persists it to the database.
    """
    email = f'new_{uuid4().hex}@mail.com'
    user_create = UserCreate(email=email, password='secure!')
    user = await UserService.create_user(db_session, user_create)
    assert user.email == email
    res = await db_session.execute(select(User).where(User.email == email))
    assert res.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_create_user_already_exists(db_session: Any, sample_user: Any) -> None:
    """
    Verify UserService.create_user raises UserAlreadyExists for a duplicate email.
    """
    user_create = UserCreate(email=sample_user.email, password='secure!')
    with pytest.raises(UserAlreadyExists):
        await UserService.create_user(db_session, user_create)


@pytest.mark.asyncio
async def test_authenticate_user_success(db_session: Any, sample_user: Any) -> None:
    """Verify authenticate_user returns the user for correct credentials."""
    user = await UserService.authenticate_user(
        db_session, sample_user.email, 'password123'
    )
    assert user is not None
    assert user.id == sample_user.id


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password(
    db_session: Any, sample_user: Any
) -> None:
    """Verify authenticate_user returns None for an incorrect password."""
    user = await UserService.authenticate_user(db_session, sample_user.email, 'wrong')
    assert user is None


@pytest.mark.asyncio
async def test_authenticate_user_not_found(db_session: Any) -> None:
    """Verify authenticate_user returns None for a nonexistent email."""
    user = await UserService.authenticate_user(db_session, 'nobody@mail.com', 'wrong')
    assert user is None


@pytest.mark.asyncio
async def test_create_and_refresh_access_token(
    db_session: Any, sample_user: Any
) -> None:
    """Verify creating a refresh token and exchanging it for a new access token."""
    token = await UserService.create_refresh_token(db_session, sample_user.id)
    assert token is not None
    user = await UserService.refresh_access_token(db_session, token)
    assert user.id == sample_user.id
    res = await db_session.execute(
        select(RefreshToken).where(RefreshToken.token == token)
    )
    assert res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_refresh_token_not_found(db_session: Any) -> None:
    """Verify refresh_access_token raises CredentialsError for an invalid token."""
    with pytest.raises(CredentialsError):
        await UserService.refresh_access_token(db_session, 'invalid_token')


@pytest.mark.asyncio
async def test_refresh_token_expired(db_session: Any, sample_user: Any) -> None:
    """Verify refresh_access_token raises CredentialsError for an expired token."""

    token = secrets.token_urlsafe(32)
    expired_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    rt = RefreshToken(
        id=uuid4(), user_id=sample_user.id, token=token, expires_at=expired_at
    )
    db_session.add(rt)
    await db_session.commit()

    with pytest.raises(CredentialsError):
        await UserService.refresh_access_token(db_session, token)


@pytest.mark.asyncio
async def test_delete_api_key_b2b_partner_success(
    db_session: Any, sample_user: Any
) -> None:
    """Verify delete_api_key_b2b_partner removes the key from the database."""
    api_key, _ = await UserService.create_api_key_b2b_partner(
        db_session, sample_user.id, 'delete_me'
    )
    await UserService.delete_api_key_b2b_partner(db_session, sample_user.id, api_key.id)

    res = await db_session.execute(
        select(APIKeyB2BPartner).where(APIKeyB2BPartner.id == api_key.id)
    )
    assert res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_api_key_b2b_partner_not_found(
    db_session: Any, sample_user: Any
) -> None:
    """Verify delete_api_key_b2b_partner raises NotFoundError for a nonexistent key."""
    with pytest.raises(NotFoundError):
        await UserService.delete_api_key_b2b_partner(
            db_session, sample_user.id, uuid4()
        )


@pytest.mark.asyncio
async def test_create_verification_request_success(
    db_session: Any, sample_user: Any
) -> None:
    """Verify create_verification_request creates a pending verification request."""
    req = await UserService.create_verification_request(
        db_session, sample_user.id, UserRole.SELLER, {'doc': 'url'}
    )
    assert req.target_role == UserRole.SELLER
    assert req.status == VerificationStatus.PENDING


@pytest.mark.asyncio
async def test_create_verification_request_already_exists(
    db_session: Any, sample_user: Any
) -> None:
    """
    Verify create_verification_request raises.
    VerificationRequestAlreadyExists on duplicate.
    """
    await UserService.create_verification_request(
        db_session, sample_user.id, UserRole.SELLER
    )
    with pytest.raises(VerificationRequestAlreadyExists):
        await UserService.create_verification_request(
            db_session, sample_user.id, UserRole.SELLER
        )


@pytest.mark.asyncio
async def test_create_verification_request_admin_role_denied(
    db_session: Any, sample_user: Any
) -> None:
    """
    Verify create_verification_request raises.
    PermissionDeniedError for administrative roles.
    """
    with pytest.raises(PermissionDeniedError) as exc:
        await UserService.create_verification_request(
            db_session, sample_user.id, UserRole.ADMIN
        )
    assert 'administrative' in str(exc.value)

    with pytest.raises(PermissionDeniedError):
        await UserService.create_verification_request(
            db_session, sample_user.id, UserRole.MODERATOR
        )


@pytest.mark.asyncio
async def test_authenticate_api_key_b2b_partner_success(
    db_session: Any, sample_user: Any
) -> None:
    """
    Verify authenticate_api_key_b2b_partner returns the key and updates last_used_at.
    """
    _, raw_key = await UserService.create_api_key_b2b_partner(
        db_session, sample_user.id, 'auth_test_key'
    )
    api_key_obj = await UserService.authenticate_api_key_b2b_partner(
        db_session, raw_key
    )
    assert api_key_obj is not None
    assert api_key_obj.user_id == sample_user.id
    assert api_key_obj.last_used_at is not None


@pytest.mark.asyncio
async def test_authenticate_api_key_b2b_partner_invalid_key(
    db_session: Any, sample_user: Any
) -> None:
    """
    Verify authenticate_api_key_b2b_partner returns.
    None for a key with a mismatching suffix.
    """
    _, raw_key = await UserService.create_api_key_b2b_partner(
        db_session, sample_user.id, 'auth_test_key_2'
    )
    invalid_key = raw_key[:12] + 'wrong_suffix'
    api_key_obj = await UserService.authenticate_api_key_b2b_partner(
        db_session, invalid_key
    )
    assert api_key_obj is None


@pytest.mark.asyncio
async def test_authenticate_api_key_b2b_partner_not_found(db_session: Any) -> None:
    """
    Verify authenticate_api_key_b2b_partner returns None for a completely unknown key.
    """
    nonexistent_key = 'some_random_key_prefix' + 'and_suffix'
    api_key_obj = await UserService.authenticate_api_key_b2b_partner(
        db_session, nonexistent_key
    )
    assert api_key_obj is None
