from http import HTTPStatus
from uuid import uuid4

from locust import HttpUser


class BaseUser(HttpUser):
    """
    Base class for all load testing scenarios.
    Contains registration and authorization logic.
    Descendants define wait_time and @task methods.
    """

    abstract = True

    def on_start(self) -> None:
        self.access_token: str | None = None
        email = f'locust_{uuid4()}@mail.com'
        password = '12345'

        with self.client.post(
            '/api/v1/users',
            json={'email': email, 'password': password},
            catch_response=True,
        ) as reg_res:
            if reg_res.status_code not in (
                HTTPStatus.OK,
                HTTPStatus.CREATED,
                HTTPStatus.BAD_REQUEST,
            ):
                reg_res.failure(f'Registration failed: {reg_res.status_code}')
                return

        with self.client.post(
            '/api/v1/auth/token',
            data={'username': email, 'password': password},
            catch_response=True,
        ) as token_res:
            if token_res.status_code == HTTPStatus.OK:
                self.access_token = token_res.json().get('access_token')
            else:
                token_res.failure(f'Login failed: {token_res.status_code}')

    @property
    def auth_headers(self) -> dict[str, str]:
        return {
            'Authorization': f'Bearer {self.access_token}',
            'X-Idempotency-Key': str(uuid4()),
        }
