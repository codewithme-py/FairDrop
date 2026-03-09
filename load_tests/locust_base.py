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
        self.refresh_token: str | None = None
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
                token_data = token_res.json()
                self.access_token = token_data.get('access_token')
                self.refresh_token = token_data.get('refresh_token')
            else:
                token_res.failure(f'Login failed: {token_res.status_code}')

    @property
    def auth_headers(self) -> dict[str, str]:
        return {
            'Authorization': f'Bearer {self.access_token}',
            'X-Idempotency-Key': str(uuid4()),
        }

    def do_get_presigned_url(
        self,
        product_id: str,
        filename: str,
        content_type: str,
    ) -> str | None:
        with self.client.post(
            f'/api/v1/media/products/{product_id}/upload_url',
            headers=self.auth_headers,
            json={'filename': filename, 'content_type': content_type},
            catch_response=True,
        ) as res:
            if res.status_code in (
                HTTPStatus.OK,
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.BAD_REQUEST,
            ):
                res.success()
                try:
                    url = res.json().get('presigned_url')
                    return str(url) if url else None
                except Exception:
                    return None
            else:
                res.failure(f'Get presigned url failed: {res.status_code}')
                return None

    def do_reserve(self, product_id: str, quantity: int = 1) -> str | None:
        with self.client.post(
            '/api/v1/inventory/reserve',
            headers=self.auth_headers,
            json={'product_id': product_id, 'quantity': quantity},
            catch_response=True,
        ) as res:
            if res.status_code in (
                HTTPStatus.OK,
                HTTPStatus.CREATED,
                HTTPStatus.CONFLICT,
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.BAD_REQUEST,
            ):
                res.success()
                if res.status_code in (HTTPStatus.OK, HTTPStatus.CREATED):
                    try:
                        res_id = res.json().get('id')
                        return str(res_id) if res_id is not None else None
                    except Exception:
                        pass
                return None
            else:
                res.failure(f'Reserve failed: {res.status_code}')
                return None

    def do_create_order(self, reservation_id: str) -> bool:
        with self.client.post(
            '/api/v1/orders/',
            headers=self.auth_headers,
            json={'reservation_id': reservation_id},
            catch_response=True,
        ) as res:
            if res.status_code in (
                HTTPStatus.CREATED,
                HTTPStatus.OK,
                HTTPStatus.TOO_MANY_REQUESTS,
            ):
                res.success()
                return True
            else:
                res.failure(f'Order failed: {res.status_code}')
                return False

    def do_view_profile(self) -> bool:
        with self.client.get(
            '/api/v1/users/me',
            headers=self.auth_headers,
            catch_response=True,
        ) as res:
            if res.status_code in (
                HTTPStatus.OK,
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.BAD_REQUEST,
            ):
                res.success()
                return True
            else:
                res.failure(f'Profile view failed: {res.status_code}')
                return False

    def do_refresh_token(self) -> bool:
        if not self.refresh_token:
            return False
        with self.client.post(
            '/api/v1/auth/refresh',
            headers=self.auth_headers,
            json={'refresh_token': self.refresh_token},
            catch_response=True,
        ) as res:
            if res.status_code == HTTPStatus.OK:
                token_data = res.json()
                self.access_token = token_data.get('access_token')
                self.refresh_token = token_data.get('refresh_token')
                res.success()
                return True
            elif res.status_code in (
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.BAD_REQUEST,
            ):
                res.success()
                return False
            else:
                res.failure(f'Token refresh failed: {res.status_code}')
                return False
