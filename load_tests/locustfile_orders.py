from locust import between, task

from load_tests.locust_base import BaseUser

TARGET_PRODUCT_ID = '5995fa75-07c7-4b55-82b7-6bfbb52948b8'


class OrderLoadUser(BaseUser):
    wait_time = between(1, 3)

    @task
    def reserve_and_order(self) -> None:
        if not self.access_token:
            return
        reservation_id = self.do_reserve(TARGET_PRODUCT_ID)
        if reservation_id:
            self.do_create_order(reservation_id)
