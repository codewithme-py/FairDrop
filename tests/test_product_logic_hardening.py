from collections.abc import Callable
from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.services.inventory.models import Product, ProductStatus
from app.services.user.models import UserRole


@pytest.mark.asyncio
async def test_update_product_status_logic(
    async_client: AsyncClient,
    db_session: AsyncSession,
    create_test_user: Callable,
    create_test_product: Callable,
) -> None:
    """Verify product updates blocked during moderation trigger re-moderation."""
    user = await create_test_user(role=UserRole.SELLER, email_prefix='harden')
    user_id = user.id
    token = create_access_token({'sub': user.email, 'role': user.role})
    headers = {'Authorization': f'Bearer {token}'}
    product = await create_test_product(owner_id=user_id)
    product_id = product.id
    await db_session.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(status=ProductStatus.PENDING_MODERATION)
    )
    await db_session.commit()
    resp = await async_client.patch(
        f'/api/v1/inventory/{product_id}',
        json={'name': 'New Name'},
        headers=headers,
    )
    assert resp.status_code == HTTPStatus.CONFLICT
    assert 'under moderation' in resp.json()['detail']
    await db_session.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(status=ProductStatus.ACTIVE)
    )
    await db_session.commit()
    resp = await async_client.patch(
        f'/api/v1/inventory/{product_id}',
        json={'price': '99.99'},
        headers=headers,
    )
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['status'] == 'PENDING_MODERATION'
    assert data['price'] == '99.99'
    assert 'image_urls' in data
