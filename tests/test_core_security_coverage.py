from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import CredentialsError, PermissionDeniedError
from app.core.security import (
    check_ownership,
    check_permission,
    create_access_token,
    get_b2b_partner_by_api_key,
)
from app.services.user.models import User, UserRole


@pytest.mark.asyncio
async def test_get_b2b_partner_by_api_key_empty() -> None:
    """Verify get_b2b_partner_by_api_key raises error for empty API key."""
    with pytest.raises(CredentialsError, match='API key is required'):
        await get_b2b_partner_by_api_key(None, MagicMock())


@pytest.mark.asyncio
@patch(
    'app.services.user.service.UserService.authenticate_api_key_b2b_partner',
    new_callable=AsyncMock,
)
async def test_get_b2b_partner_by_api_key_invalid(mock_auth: Any) -> None:
    """Verify get_b2b_partner_by_api_key raises error for an invalid API key."""
    mock_auth.return_value = None
    with pytest.raises(CredentialsError, match='Invalid API key'):
        await get_b2b_partner_by_api_key('bad_key', MagicMock())


@pytest.mark.asyncio
@patch(
    'app.services.user.service.UserService.authenticate_api_key_b2b_partner',
    new_callable=AsyncMock,
)
async def test_get_b2b_partner_by_api_key_inactive(mock_auth: Any) -> None:
    """Verify get_b2b_partner_by_api_key raises error for an inactive user."""
    u = User(is_active=False)
    mo = MagicMock()
    mo.user = u
    mock_auth.return_value = mo
    with pytest.raises(CredentialsError, match='User is not active'):
        await get_b2b_partner_by_api_key('key', MagicMock())


@pytest.mark.asyncio
@patch(
    'app.services.user.service.UserService.authenticate_api_key_b2b_partner',
    new_callable=AsyncMock,
)
async def test_get_b2b_partner_by_api_key_wrong_role(mock_auth: Any) -> None:
    """Verify get_b2b_partner_by_api_key raises error for non-B2B role."""
    u = User(is_active=True, role=UserRole.USER)
    mo = MagicMock()
    mo.user = u
    mock_auth.return_value = mo
    with pytest.raises(CredentialsError, match='Not a B2B partner account'):
        await get_b2b_partner_by_api_key('key', MagicMock())


@pytest.mark.asyncio
@patch(
    'app.services.user.service.UserService.authenticate_api_key_b2b_partner',
    new_callable=AsyncMock,
)
async def test_get_b2b_partner_by_api_key_success(mock_auth: Any) -> None:
    """Verify get_b2b_partner_by_api_key returns the user for valid B2B credentials."""
    u = User(is_active=True, role=UserRole.SELLER_B2B)
    mo = MagicMock()
    mo.user = u
    mock_auth.return_value = mo
    res = await get_b2b_partner_by_api_key('key', MagicMock())
    assert res == u


def test_create_access_token_expires_delta() -> None:
    """Verify create_access_token produces a valid JWT string with an expiry delta."""
    tok = create_access_token({'sub': 'test'}, timedelta(minutes=5))
    assert isinstance(tok, str)


@pytest.mark.asyncio
async def test_check_permission() -> None:
    """Verify check_permission raises for unverified users and disallowed roles."""
    u = User(role=UserRole.USER, is_verified=False)
    with pytest.raises(PermissionDeniedError, match='User is not verified'):
        await check_permission(u, [UserRole.USER], required_verified=True)

    with pytest.raises(PermissionDeniedError, match='User does not have permission'):
        await check_permission(u, [UserRole.ADMIN])


def test_check_ownership() -> None:
    """Verify check_ownership validates owner_id presence and enforces ownership."""
    u = User(id=uuid4(), role=UserRole.USER)

    class Missing:
        pass

    with pytest.raises(ValueError, match='does not have owner_id or user_id'):
        check_ownership(u, Missing())

    class BadOwner:
        owner_id = uuid4()

    with pytest.raises(PermissionDeniedError):
        check_ownership(u, BadOwner())

    class GoodOwner:
        owner_id = u.id

    check_ownership(u, GoodOwner())
