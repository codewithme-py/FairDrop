from http import HTTPStatus

from locust import between, task

from locust_base import BaseUser

OVERSELL_PRODUCT_ID = '3fe44185-589a-4703-b640-40df8d7ea67f'


class OversellTestUser(BaseUser):
    wait_time = between(0.1, 0.5)

    @task
    def reserve_oversell_product(self) -> None:
        if not self.access_token:
            return
        with self.client.post(
            '/api/v1/inventory/reserve',
            headers=self.auth_headers,
            json={'product_id': OVERSELL_PRODUCT_ID, 'quantity': 1},
            catch_response=True,
        ) as reserve_res:
            if reserve_res.status_code not in (
                HTTPStatus.OK,
                HTTPStatus.CREATED,
                HTTPStatus.CONFLICT,
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.BAD_REQUEST,
            ):
                reserve_res.failure(f'Reserve failed: {reserve_res.status_code}')
