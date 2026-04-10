from http import HTTPStatus
from typing import Any

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.services.orders.models import OrderStatus
from app.services.user.models import UserRole


@pytest.mark.asyncio
async def test_buyer_stats_aggregation(
    async_client: AsyncClient, create_test_user: Any, create_test_order: Any
) -> None:
    """Verify buyer order stats are correctly aggregated by status."""
    buyer = await create_test_user(UserRole.USER)
    token = create_access_token({'sub': buyer.email, 'role': buyer.role})
    headers = {'Authorization': f'Bearer {token}'}
    await create_test_order(buyer.id, OrderStatus.PENDING, '100')
    await create_test_order(buyer.id, OrderStatus.PAID, '200')
    await create_test_order(buyer.id, OrderStatus.SHIPPED, '300')
    resp = await async_client.get('/api/v1/buyer_user/stats', headers=headers)
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['total_orders'] == 3
    assert data['pending_orders'] == 1
    assert data['paid_orders'] == 1
    assert data['shipped_orders'] == 1


@pytest.mark.asyncio
async def test_buyer_orders_filtering(
    async_client: AsyncClient, create_test_user: Any, create_test_order: Any
) -> None:
    """Verify buyer orders can be filtered by status."""
    buyer = await create_test_user(UserRole.USER)
    token = create_access_token({'sub': buyer.email, 'role': buyer.role})
    headers = {'Authorization': f'Bearer {token}'}
    await create_test_order(buyer.id, OrderStatus.PENDING, '100')
    await create_test_order(buyer.id, OrderStatus.PAID, '200')
    resp = await async_client.get('/api/v1/buyer_user/orders', headers=headers)
    assert resp.status_code == HTTPStatus.OK
    assert len(resp.json()) == 2

    resp = await async_client.get(
        '/api/v1/buyer_user/orders?status=PAID', headers=headers
    )
    assert len(resp.json()) == 1
    assert resp.json()[0]['status'] == 'PAID'

    resp = await async_client.get(
        '/api/v1/buyer_user/orders?status=CANCELLED', headers=headers
    )
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_buyer_empty_dashboard(
    async_client: AsyncClient, create_test_user: Any
) -> None:
    """Verify buyer stats and orders return empty results when no orders exist."""
    buyer = await create_test_user(UserRole.USER)
    token = create_access_token({'sub': buyer.email, 'role': buyer.role})
    headers = {'Authorization': f'Bearer {token}'}
    resp = await async_client.get('/api/v1/buyer_user/stats', headers=headers)
    assert resp.json()['total_orders'] == 0
    resp = await async_client.get('/api/v1/buyer_user/orders', headers=headers)
    assert resp.json() == []
