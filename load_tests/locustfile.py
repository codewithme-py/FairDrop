from http import HTTPStatus

from locust import between, task

from load_tests.locust_base import BaseUser

TARGET_PRODUCT_ID = '5995fa75-07c7-4b55-82b7-6bfbb52948b8'


class HighLoadUser(BaseUser):
    wait_time = between(0.5, 2.0)

    @task
    def reserve_product(self) -> None:
        if not self.access_token:
            return
        with self.client.post(
            '/api/v1/inventory/reserve',
            headers=self.auth_headers,
            json={'product_id': TARGET_PRODUCT_ID, 'quantity': 1},
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
