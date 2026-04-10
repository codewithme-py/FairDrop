from locust import between, task

from load_tests.locust_base import BaseUser

TARGET_PRODUCT_ID = '5995fa75-07c7-4b55-82b7-6bfbb52948b8'


class HighLoadUser(BaseUser):
    """
    High-throughput user sending reserve requests at a fast pace.

    Uses short wait times (0.5-2.0 seconds) to generate significant load
    on the inventory reservation endpoint.
    """

    wait_time = between(0.5, 2.0)

    @task
    def reserve_product(self) -> None:
        """
        Reserve a unit of the target product.

        Skips if the user is not authenticated.
        """
        if not self.access_token:
            return
        self.do_reserve(TARGET_PRODUCT_ID)
