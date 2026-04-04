from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, Request

from app.shared.rate_limit import (
    GLOBAL_EXCEEDED_LIMIT,
    USER_EXCEEDED_LIMIT,
    check_rate_limit,
)
from app.shared.rate_limit_utils import limit_login_attempts, limit_signup_attempts


@pytest.fixture
def mock_script() -> Any:
    return AsyncMock()


@pytest.fixture
def mock_request(mock_script: Any) -> Any:
    request = Mock(spec=Request)
    request.app = Mock()
    request.app.state = Mock()
    request.app.state.rate_limit_script = mock_script
    request.client = Mock()
    request.client.host = '192.168.1.1'
    return request


@pytest.mark.asyncio
async def test_check_rate_limit_success(mock_script: Any) -> None:
    mock_script.return_value = 1
    res = await check_rate_limit(mock_script, keys=['key'], limits=[10])
    assert res is True
    # Verify that a dummy key was added since length was 1
    mock_script.assert_called_once()
    kwargs = mock_script.call_args.kwargs
    assert len(kwargs['keys']) == 2
    assert kwargs['keys'][1] == 'rate_limit:dummy:key'


@pytest.mark.asyncio
async def test_check_rate_limit_user_exceeded(mock_script: Any) -> None:
    mock_script.return_value = 0
    with pytest.raises(HTTPException) as exc:
        await check_rate_limit(mock_script, keys=['k1', 'k2'], limits=[10, 100])
    assert exc.value.status_code == 429
    assert exc.value.detail == USER_EXCEEDED_LIMIT


@pytest.mark.asyncio
async def test_check_rate_limit_global_exceeded(mock_script: Any) -> None:
    mock_script.return_value = -1
    with pytest.raises(HTTPException) as exc:
        await check_rate_limit(mock_script, keys=['k1', 'k2'], limits=[10, 100])
    assert exc.value.status_code == 429
    assert exc.value.detail == GLOBAL_EXCEEDED_LIMIT


@pytest.mark.asyncio
async def test_limit_login_attempts(mock_request: Any, mock_script: Any) -> None:
    mock_script.return_value = 1
    await limit_login_attempts(mock_request, 'test@mail.com')
    mock_script.assert_called_once()
    kwargs = mock_script.call_args.kwargs
    assert kwargs['keys'][0] == 'rate_limit:login:test@mail.com'


@pytest.mark.asyncio
async def test_limit_signup_attempts(mock_request: Any, mock_script: Any) -> None:
    mock_script.return_value = 1
    await limit_signup_attempts(mock_request)
    mock_script.assert_called_once()
    kwargs = mock_script.call_args.kwargs
    assert kwargs['keys'][0] == 'rate_limit:signup:192.168.1.1'


@pytest.mark.asyncio
async def test_limit_signup_attempts_no_client(
    mock_request: Any, mock_script: Any
) -> None:
    mock_request.client = None
    mock_script.return_value = 1
    await limit_signup_attempts(mock_request)
    mock_script.assert_called_once()
    kwargs = mock_script.call_args.kwargs
    assert kwargs['keys'][0] == 'rate_limit:signup:unknown'
