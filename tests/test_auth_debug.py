from http import HTTPStatus
from typing import Any

import pytest
from jose import jwt
from sqlalchemy import select

from app.core.config import settings
from app.services.user.models import User


@pytest.mark.asyncio
async def test_auth_debug_raw(db_session: Any, admin_headers: Any) -> None:
    token = admin_headers['Authorization'].split(' ')[1]
    payload = jwt.decode(
        token, settings.secret_key, algorithms=[settings.jwt_algorithm]
    )
    sub_email = payload['sub']
    print(f'\n[DEBUG] Testing with email: {sub_email}')
    result = await db_session.execute(select(User).where(User.email == sub_email))
    user = result.scalar_one_or_none()
    assert user is not None, f'User {sub_email} should exist in DB'
    print(f'[DEBUG] User found in session DB: {user.id}')


@pytest.mark.asyncio
async def test_auth_via_client(async_client: Any, admin_headers: Any) -> None:
    resp = await async_client.get('/api/v1/users/me', headers=admin_headers)
    print(f'[DEBUG] Response status: {resp.status_code}')
    print(f'[DEBUG] Response body: {resp.text}')
    assert resp.status_code == HTTPStatus.OK
