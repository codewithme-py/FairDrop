from typing import Any
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request, Response
from jose import jwt
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import CredentialsError, PermissionDeniedError
from app.services.user.models import User, UserRole
from app.shared.decorators import idempotent
from app.shared.deps import get_api_key_user, get_current_user


class MockResponse(BaseModel):
    id: str
    name: str


@pytest.fixture
async def sample_user(db_session: Any) -> Any:
    user = User(
        id=uuid4(),
        email=f'shared_{uuid4().hex[:4]}@mail.com',
        password_hash='hashed_password',
        role=UserRole.USER,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def create_mock_request(
    method: str = 'POST', path: str = '/test', headers: Any = None
) -> Request:
    scope = {
        'type': 'http',
        'method': method,
        'path': path,
        'headers': [
            (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
        ],
        'app': Mock(),
    }
    request = Request(scope=scope)
    request.app.state.redis = AsyncMock()
    return request


@pytest.mark.asyncio
async def test_get_current_user_no_sub(db_session: Any) -> None:
    token = jwt.encode(
        {'foo': 'bar'}, settings.secret_key, algorithm=settings.jwt_algorithm
    )
    with pytest.raises(CredentialsError):
        await get_current_user(token, db_session)


@pytest.mark.asyncio
async def test_get_current_user_not_found(db_session: Any) -> None:
    token = jwt.encode(
        {'sub': 'nonexistent@mail.com'},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(CredentialsError):
        await get_current_user(token, db_session)


@pytest.mark.asyncio
async def test_get_api_key_user_missing(db_session: Any) -> None:
    with pytest.raises(PermissionDeniedError) as exc:
        await get_api_key_user(None, db_session)
    assert 'Missing API Key' in str(exc.value)


@pytest.mark.asyncio
async def test_get_api_key_user_invalid(db_session: Any) -> None:
    with pytest.raises(PermissionDeniedError) as exc:
        await get_api_key_user('invalid_key', db_session)
    assert 'Invalid API Key' in str(exc.value)


@pytest.mark.asyncio
async def test_idempotent_no_request() -> None:
    @idempotent()
    async def foo(a: int, b: int) -> int:
        return a + b

    res = await foo(1, 2)
    assert res == 3


@pytest.mark.asyncio
async def test_idempotent_missing_header() -> None:
    request = create_mock_request(headers={})

    @idempotent()
    async def foo(request: Request) -> dict[str, bool]:
        return {'ok': True}

    with pytest.raises(HTTPException) as exc:
        await foo(request)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_idempotent_cache_hit() -> None:
    request = create_mock_request(headers={'x-idempotency-key': 'test_key'})
    request.app.state.redis.get.return_value = b'{"ok": true}'

    @idempotent()
    async def foo(request: Request) -> dict[str, str]:
        return {'not': 'reached'}

    res = await foo(request)
    assert isinstance(res, Response)
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_idempotent_cache_miss_pydantic() -> None:
    request = create_mock_request(headers={'x-idempotency-key': 'new_key'})
    request.app.state.redis.get.return_value = None

    @idempotent()
    async def foo(request: Request) -> MockResponse:
        return MockResponse(id='123', name='test')

    res = await foo(request)
    assert isinstance(res, MockResponse)
    request.app.state.redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_get_current_user_success(db_session: Any, sample_user: Any) -> None:
    # Valid token
    token = jwt.encode(
        {'sub': sample_user.email},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    res = await get_current_user(token, db_session)
    assert res.id == sample_user.id


@pytest.mark.asyncio
async def test_get_current_user_jwt_error(db_session: Any) -> None:
    # Token with invalid signature
    token = jwt.encode(
        {'sub': 'test@mail.com'}, 'wrong_secret', algorithm=settings.jwt_algorithm
    )
    with pytest.raises(CredentialsError):
        await get_current_user(token, db_session)


@pytest.mark.asyncio
async def test_get_api_key_user_success(db_session: Any, sample_user: Any) -> None:
    from app.services.user.service import UserService

    api_key_obj, raw_key = await UserService.create_api_key_b2b_partner(
        db_session, sample_user.id, 'Test Key'
    )
    res = await get_api_key_user(raw_key, db_session)
    assert res.id == sample_user.id


@pytest.mark.asyncio
async def test_idempotent_request_in_kwargs() -> None:
    request = create_mock_request(headers={'x-idempotency-key': 'kw_key'})
    request.app.state.redis.get.return_value = None

    @idempotent()
    async def foo(request: Request) -> dict[str, bool]:
        return {'ok': True}

    # Pass as kwarg
    res = await foo(request=request)
    assert res == {'ok': True}
    request.app.state.redis.setex.assert_called_once()
