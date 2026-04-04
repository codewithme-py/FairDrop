from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.exceptions import PermissionDeniedError, VerificationRequestAlreadyExists
from app.services.user.models import UserRole
from app.services.user.service import UserService


@pytest.mark.asyncio
async def test_user_signup_and_duplicate(async_client: AsyncClient) -> None:
    """Verify signup success and conflict on duplicate email."""
    email = f'u_{uuid4().hex[:6]}@test.com'
    payload = {'email': email, 'password': 'password123'}
    resp = await async_client.post('/api/v1/users', json=payload)
    assert resp.status_code == HTTPStatus.CREATED
    resp = await async_client.post('/api/v1/users', json=payload)
    assert resp.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.asyncio
async def test_user_login_flow(async_client: AsyncClient) -> None:
    """Verify login success and credentials error."""
    email = f'u_{uuid4().hex[:6]}@test.com'
    await async_client.post('/api/v1/users', json={'email': email, 'password': 'p'})
    resp = await async_client.post(
        '/api/v1/auth/token', data={'username': email, 'password': 'p'}
    )
    assert resp.status_code == HTTPStatus.OK
    resp = await async_client.post(
        '/api/v1/auth/token', data={'username': email, 'password': 'wrong'}
    )
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_token_refresh_cycle(async_client: AsyncClient) -> None:
    """Verify full refresh token cycle and error on fake token."""
    email = f'u_{uuid4().hex[:6]}@test.com'
    await async_client.post('/api/v1/users', json={'email': email, 'password': 'p'})
    login_resp = await async_client.post(
        '/api/v1/auth/token', data={'username': email, 'password': 'p'}
    )
    refresh_token = login_resp.json()['refresh_token']
    resp = await async_client.post(
        '/api/v1/auth/refresh', json={'refresh_token': refresh_token}
    )
    assert resp.status_code == HTTPStatus.OK
    resp = await async_client.post(
        '/api/v1/auth/refresh', json={'refresh_token': 'fake'}
    )
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_b2b_api_keys_full_cycle(
    async_client: AsyncClient, b2b_user_headers: dict
) -> None:
    """Verify B2B API keys management."""
    resp = await async_client.post(
        '/api/v1/users/me/api-keys', json={'name': 'K'}, headers=b2b_user_headers
    )
    assert resp.status_code == HTTPStatus.CREATED
    kid = resp.json()['id']
    resp = await async_client.get('/api/v1/users/me/api-keys', headers=b2b_user_headers)
    assert resp.status_code == HTTPStatus.OK
    await async_client.delete(
        f'/api/v1/users/me/api-keys/{kid}', headers=b2b_user_headers
    )
    resp = await async_client.delete(
        f'/api/v1/users/me/api-keys/{kid}', headers=b2b_user_headers
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_upgrade_request_validation(
    async_client: AsyncClient, buyer_headers: dict
) -> None:
    """Verify upgrade request basic flow and schema validation."""
    payload = {'target_role': UserRole.SELLER_B2B}
    resp = await async_client.post(
        '/api/v1/users/me/upgrade-requests', json=payload, headers=buyer_headers
    )
    assert resp.status_code == HTTPStatus.CREATED
    resp = await async_client.post(
        '/api/v1/users/me/upgrade-requests', json=payload, headers=buyer_headers
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    resp = await async_client.post(
        '/api/v1/users/me/upgrade-requests',
        json={'target_role': 'admin'},
        headers=buyer_headers,
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_service_upgrade_denied_role() -> None:
    """Directly test UserService for administrative role denial."""
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_result.scalar_one_or_none.return_value = None
    with pytest.raises(PermissionDeniedError):
        await UserService.create_verification_request(
            mock_session, uuid4(), UserRole.ADMIN
        )


@pytest.mark.asyncio
async def test_service_upgrade_duplicate_check() -> None:
    """Directly test UserService for duplicate request check."""
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_result.scalar_one_or_none.return_value = MagicMock()
    with pytest.raises(VerificationRequestAlreadyExists):
        await UserService.create_verification_request(
            mock_session, uuid4(), UserRole.SELLER_B2B
        )


@pytest.mark.asyncio
async def test_service_auth_none() -> None:
    """Test authenticate_user returns None for bad credentials."""
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_result.scalar_one_or_none.return_value = None
    res = await UserService.authenticate_user(mock_session, 'u@t.com', 'p')
    assert res is None
