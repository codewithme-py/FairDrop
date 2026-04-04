from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.worker import shutdown, startup


@pytest.mark.asyncio
async def test_worker_startup_success() -> None:
    """Verify that worker startup initializes session_maker and logs correctly."""
    ctx: dict[str, Any] = {}
    with (
        patch('app.worker.create_async_engine') as mock_engine_create,
        patch('app.worker.async_sessionmaker') as mock_sessionmaker,
    ):
        mock_engine = MagicMock()
        mock_engine_create.return_value = mock_engine
        await startup(ctx)
        assert 'session_maker' in ctx
        assert mock_engine_create.called
        assert mock_sessionmaker.called


@pytest.mark.asyncio
async def test_worker_shutdown() -> None:
    """Verify worker shutdown disposes the engine."""
    mock_engine = AsyncMock()
    mock_session_maker = MagicMock()
    mock_session_maker.kw = {'bind': mock_engine}
    ctx: dict[str, Any] = {'session_maker': mock_session_maker}
    await shutdown(ctx)
    assert mock_engine.dispose.called


@pytest.mark.asyncio
async def test_worker_startup_failure_logs() -> None:
    """Verify startup failure is logged and re-raised."""
    ctx: dict[str, Any] = {}
    with patch('app.worker.create_async_engine', side_effect=Exception('Conn error')):
        with pytest.raises(Exception) as exc:
            await startup(ctx)
        assert 'Conn error' in str(exc.value)
