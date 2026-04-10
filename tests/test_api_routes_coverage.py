from http import HTTPStatus
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_full_platform_flow(
    async_client: AsyncClient,
    admin_headers: dict,
    seller_headers: dict,
    buyer_headers: dict,
) -> None:
    """Verify the full platform flow: create, approve, reserve, and order."""
    p_payload = {'name': f'P_{uuid4().hex[:4]}', 'price': 10.0, 'qty_available': 10}
    resp = await async_client.post(
        '/api/v1/inventory/', json=p_payload, headers=seller_headers
    )
    assert resp.status_code == HTTPStatus.CREATED
    pid = resp.json()['id']
    await async_client.post(f'/api/v1/inventory/{pid}/submit', headers=seller_headers)
    await async_client.post(f'/api/v1/inventory/{pid}/claim', headers=admin_headers)
    await async_client.post(f'/api/v1/inventory/{pid}/approve', headers=admin_headers)
    res_payload = {'product_id': pid, 'quantity': 1}
    r_headers = {**buyer_headers, 'X-Idempotency-Key': uuid4().hex}
    resp = await async_client.post(
        '/api/v1/inventory/reserve', json=res_payload, headers=r_headers
    )
    assert resp.status_code == HTTPStatus.OK
    rid = resp.json()['id']
    order_payload = {'reservation_id': str(rid), 'shipping_address': 'Test'}
    o_headers = {**buyer_headers, 'X-Idempotency-Key': uuid4().hex}
    resp = await async_client.post(
        '/api/v1/orders/', json=order_payload, headers=o_headers
    )
    assert resp.status_code in (HTTPStatus.OK, HTTPStatus.CREATED), (
        f'Order creation failed: {resp.text}'
    )


@pytest.mark.asyncio
async def test_inventory_seller_limits_enforced(
    async_client: AsyncClient, unverified_seller_headers: dict
) -> None:
    """Verify unverified sellers are limited to a maximum number of products."""
    payload = {'name': 'L', 'price': 1.0, 'qty_available': 1}
    for _ in range(3):
        resp = await async_client.post(
            '/api/v1/inventory/', json=payload, headers=unverified_seller_headers
        )
        assert resp.status_code == HTTPStatus.CREATED
    resp = await async_client.post(
        '/api/v1/inventory/', json=payload, headers=unverified_seller_headers
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST, resp.text
    assert 'Limit' in resp.json()['detail']


@pytest.mark.asyncio
async def test_rbac_and_errors(
    async_client: AsyncClient, admin_headers: dict, seller_headers: dict
) -> None:
    """Verify inventory RBAC and conflict errors for approve operations."""
    resp = await async_client.get(f'/api/v1/inventory/{uuid4()}')
    assert resp.status_code == HTTPStatus.NOT_FOUND
    p = await async_client.post(
        '/api/v1/inventory/',
        json={'name': 'C', 'price': 1.0, 'qty_available': 1},
        headers=seller_headers,
    )
    pid = p.json()['id']
    resp = await async_client.post(
        f'/api/v1/inventory/{pid}/approve', headers=admin_headers
    )
    assert resp.status_code == HTTPStatus.CONFLICT
