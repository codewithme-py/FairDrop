import asyncio
from http import HTTPStatus
from uuid import UUID, uuid4

from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.inventory.models import Product


async def test_reserve_flow(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    test_email = f'{uuid4().hex[:8]}@example.com'
    test_password = 'super_secret_password'
    test_product_id = uuid4()
    idempotency_key = uuid4().hex
    test_user_res = await async_client.post(
        '/api/v1/users', json={'email': test_email, 'password': test_password}
    )
    assert test_user_res.status_code == HTTPStatus.CREATED
    created_user_id = UUID(test_user_res.json()['id'])

    test_product = Product(
        id=test_product_id,
        owner_id=created_user_id,
        name='Hatchback 02 red',
        description='dayz car such as golf II',
        price='100',
        qty_available=100,
    )
    db_session.add(test_product)
    await db_session.commit()
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
    assert test_reserve_data['product_id'] == str(test_product_id)
    assert test_reserve_data['status'] == 'PENDING'

    test_reserve = await async_client.post(
        '/api/v1/inventory/reserve',
        json={'product_id': str(test_product_id), 'quantity': 1},
        headers=headers,
    )
    assert test_reserve.status_code == HTTPStatus.OK
    test_reserve_data = test_reserve.json()
    assert 'id' in test_reserve_data
    assert test_reserve_data['product_id'] == str(test_product_id)

    async def make_request() -> Response:
        return await async_client.post(
            '/api/v1/inventory/reserve',
            json={'product_id': str(test_product_id), 'quantity': 1},
            headers={
                'Authorization': f'Bearer {test_user_access_token}',
                'X-Idempotency-Key': uuid4().hex,
            },
        )

    responses = await asyncio.gather(*(make_request() for _ in range(50)))
    status_codes = [r.status_code for r in responses]

    assert HTTPStatus.TOO_MANY_REQUESTS in status_codes
