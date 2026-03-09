from http import HTTPStatus
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.inventory.models import Product


async def test_reserve_order_flow(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    test_email = f'{uuid4().hex[:8]}@example.com'
    test_password = 'super_secret_password'
    test_product_id = uuid4()
    idempotency_key = uuid4().hex
    test_product = Product(
        id=test_product_id,
        name='Hatchback 02 blue',
        description='dayz car such as golf II blue',
        price='150',
        qty_available=5,
    )
    db_session.add(test_product)
    await db_session.commit()
    test_user = await async_client.post(
        '/api/v1/users', json={'email': test_email, 'password': test_password}
    )
    assert test_user.status_code == HTTPStatus.CREATED
    test_user_login = await async_client.post(
        '/api/v1/auth/token', data={'username': test_email, 'password': test_password}
    )
    assert test_user_login.status_code == HTTPStatus.OK
    test_user_access_token = test_user_login.json()['access_token']
    headers = {
        'Authorization': f'Bearer {test_user_access_token}',
        'X-Idempotency-Key': idempotency_key,
    }
    test_reserve = await async_client.post(
        '/api/v1/inventory/reserve',
        json={'product_id': str(test_product_id), 'quantity': 1},
        headers=headers,
    )
    assert test_reserve.status_code == HTTPStatus.OK
    test_reserve_data = test_reserve.json()
    assert 'id' in test_reserve_data
    reservation_id = test_reserve_data['id']
    order_idempotency_key = uuid4().hex
    headers['X-Idempotency-Key'] = order_idempotency_key
    test_order = await async_client.post(
        '/api/v1/orders/', json={'reservation_id': reservation_id}, headers=headers
    )
    assert test_order.status_code == HTTPStatus.OK
    test_order_data = test_order.json()
    assert test_order_data['status'] == 'pending'
    assert test_order_data['total_amount'] == '150.00'
    assert 'id' in test_order_data
