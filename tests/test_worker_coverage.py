from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.worker import WorkerSettings, shutdown, startup


@pytest.mark.asyncio
async def test_worker_startup_success() -> None:
    ctx: dict[str, Any] = {}
    await startup(ctx)
    assert 'session_maker' in ctx
    assert ctx['session_maker'].kw['bind'] is not None


@pytest.mark.asyncio
@patch('app.worker.create_async_engine')
async def test_worker_startup_failure(mock_create_engine: Any) -> None:
    mock_create_engine.side_effect = Exception('DB error')
    ctx: dict[str, Any] = {}
    with pytest.raises(Exception, match='DB error'):
        await startup(ctx)


@pytest.mark.asyncio
async def test_worker_shutdown() -> None:
    mock_engine = Mock(spec=AsyncEngine)
    mock_engine.dispose = AsyncMock()

    mock_session_maker = Mock()
    mock_session_maker.kw = {'bind': mock_engine}

    ctx: dict[str, Any] = {'session_maker': mock_session_maker}
    await shutdown(ctx)

    mock_engine.dispose.assert_called_once()


@pytest.mark.asyncio
async def test_worker_shutdown_no_session_maker() -> None:
    ctx: dict[str, Any] = {}
    # Should not raise any errors
    await shutdown(ctx)


def test_worker_settings() -> None:
    assert WorkerSettings.on_startup == startup
    assert WorkerSettings.on_shutdown == shutdown
    assert len(WorkerSettings.cron_jobs) == 1
    assert len(WorkerSettings.functions) == 1
