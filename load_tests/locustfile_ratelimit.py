from locust import constant_pacing, task

from load_tests.locust_base import BaseUser

TARGET_PRODUCT_ID = '5995fa75-07c7-4b55-82b7-6bfbb52948b8'


class RatelimitUser(BaseUser):
    wait_time = constant_pacing(0.05)

    @task
    def spam_profile(self) -> None:
        if not self.access_token:
            return
        self.do_reserve(TARGET_PRODUCT_ID)
