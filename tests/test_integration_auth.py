from http import HTTPStatus
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio(loop_scope='session')
async def test_auth_flow(async_client: AsyncClient) -> None:
    test_email = f'{uuid4().hex[:8]}@example.com'
    test_password = 'super_secret_password'
    response = await async_client.post(
        '/api/v1/users', json={'email': test_email, 'password': test_password}
    )
    assert response.status_code == HTTPStatus.CREATED
    response_data = response.json()
    assert response_data['email'] == test_email

    response = await async_client.post(
        '/api/v1/users', json={'email': test_email, 'password': test_password}
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    response_data = response.json()
    assert 'already' in response_data['detail']

    response = await async_client.post(
        '/api/v1/auth/token', data={'username': test_email, 'password': test_password}
    )
    assert response.status_code == HTTPStatus.OK
    response_data = response.json()
    access_token = response_data['access_token']
    refresh_token = response_data['refresh_token']

    response = await async_client.post(
        '/api/v1/auth/refresh', json={'refresh_token': refresh_token}
    )
    assert response.status_code == HTTPStatus.OK
    response_data = response.json()
    access_token = response_data['access_token']

    response = await async_client.get(
        '/api/v1/users/me', headers={'Authorization': f'Bearer {access_token}'}
    )
    assert response.status_code == HTTPStatus.OK
    response_data = response.json()
    assert response_data['email'] == test_email
