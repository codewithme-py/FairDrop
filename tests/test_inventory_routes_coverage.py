from collections.abc import Callable
from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.inventory.models import Product, ProductStatus


@pytest.mark.asyncio
async def test_inventory_routes_full_coverage(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_headers: dict,
    seller_headers: dict,
    create_test_product: Callable,
) -> None:
    resp = await async_client.post(
        '/api/v1/inventory/',
        json={
            'name': 'Route Test Product',
            'description': 'Desc',
            'price': '100.00',
            'qty_available': 10,
        },
        headers=seller_headers,
    )
    assert resp.status_code == HTTPStatus.CREATED
    product_id = resp.json()['id']
    resp = await async_client.get('/api/v1/inventory/')
    assert resp.status_code == HTTPStatus.OK
    await db_session.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(status=ProductStatus.PENDING_MODERATION)
    )
    await db_session.commit()
    resp = await async_client.post(
        f'/api/v1/inventory/{product_id}/claim', headers=admin_headers
    )
    assert resp.status_code == HTTPStatus.OK
    resp = await async_client.post(
        f'/api/v1/inventory/{product_id}/reject',
        params={'reason': 'Testing rejection'},
        headers=admin_headers,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['status'] == 'REJECTED'
    await db_session.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(status=ProductStatus.MODERATION_IN_PROGRESS)
    )
    await db_session.commit()
    resp = await async_client.post(
        f'/api/v1/inventory/{product_id}/approve', headers=admin_headers
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['status'] == 'ACTIVE'
    resp = await async_client.get(f'/api/v1/inventory/{product_id}')
    assert resp.status_code == HTTPStatus.OK
    assert 'image_urls' in resp.json()
    await db_session.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(status=ProductStatus.DRAFT)
    )
    await db_session.commit()
    resp = await async_client.patch(
        f'/api/v1/inventory/{product_id}/activate', headers=admin_headers
    )
    assert resp.status_code == HTTPStatus.OK
    resp = await async_client.delete(
        f'/api/v1/inventory/{product_id}', headers=admin_headers
    )
    assert resp.status_code == HTTPStatus.NO_CONTENT
