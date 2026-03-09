from locust import between, task

from load_tests.locust_base import BaseUser

TARGET_PRODUCT_ID = '5995fa75-07c7-4b55-82b7-6bfbb52948b8'


class MixedLoadUser(BaseUser):
    wait_time = between(1.0, 3.0)

    @task(6)
    def reserve_product(self) -> None:
        if not self.access_token:
            return
        self.do_reserve(TARGET_PRODUCT_ID)

    @task(2)
    def view_profile(self) -> None:
        if not self.access_token:
            return
        self.do_view_profile()

    @task(2)
    def update_token(self) -> None:
        if not self.refresh_token:
            return
        self.do_refresh_token()
