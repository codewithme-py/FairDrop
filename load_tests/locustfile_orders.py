from http import HTTPStatus

from locust import between, task

from load_tests.locust_base import BaseUser

TARGET_PRODUCT_ID = '5995fa75-07c7-4b55-82b7-6bfbb52948b8'


class OrderLoadUser(BaseUser):
    wait_time = between(1, 3)

    @task
    def reserve_and_order(self) -> None:
        if not self.access_token:
            return
        with self.client.post(
            '/api/v1/inventory/reserve',
            headers=self.auth_headers,
            json={'product_id': TARGET_PRODUCT_ID, 'quantity': 1},
            catch_response=True,
        ) as response:
            if response.status_code not in (
                HTTPStatus.OK,
                HTTPStatus.CREATED,
                HTTPStatus.CONFLICT,
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.BAD_REQUEST,
            ):
                response.failure(f'Reserve failed: {response.status_code}')
                return
            if response.status_code not in (HTTPStatus.OK, HTTPStatus.CREATED):
                return
            reservation_id = response.json()['id']
        with self.client.post(
            '/api/v1/orders/',
            headers=self.auth_headers,
            json={'reservation_id': reservation_id},
            catch_response=True,
        ) as response:
            if response.status_code not in (HTTPStatus.CREATED, HTTPStatus.OK):
                response.failure(f'Order failed: {response.status_code}')
