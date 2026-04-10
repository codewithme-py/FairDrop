from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def mock_redis() -> Any:
    """Mock the Redis client initialization in the FastAPI app."""
    with patch('app.main.Redis.from_url') as mock:
        client = AsyncMock()
        client.register_script.return_value = 'mock_script'
        mock.return_value = client
        yield mock


@pytest.fixture
def mock_arq() -> Any:
    """Mock the ARQ connection pool initialization in the FastAPI app."""
    with patch('app.main.create_pool', new_callable=AsyncMock) as mock:
        pool = AsyncMock()
        mock.return_value = pool
        yield mock


@pytest.fixture
def mock_s3() -> Any:
    """Mock the S3 bucket initialization in the FastAPI app."""
    with patch('app.main.init_s3_bucket', new_callable=AsyncMock) as mock:
        yield mock


def test_main_endpoints_and_lifespan(
    mock_redis: Any, mock_arq: Any, mock_s3: Any
) -> None:
    """Verify health and root endpoints respond correctly during app lifespan."""
    with TestClient(app) as client:
        res_health = client.get('/health')
        assert res_health.status_code == 200
        assert res_health.json() == {'status': 'ok'}
        res_root = client.get('/')
        assert res_root.status_code == 200
        assert res_root.json() == {'message': 'Hello from fairdrop!'}


def test_add_request_context_exception(
    mock_redis: Any, mock_arq: Any, mock_s3: Any
) -> None:
    """Verify the request context middleware handles exceptions raised in routes."""

    @app.get('/_test_error')
    def test_error() -> None:
        raise RuntimeError('Test exception')

    with TestClient(app) as client:
        with pytest.raises(RuntimeError, match='Test exception'):
            client.get('/_test_error')
