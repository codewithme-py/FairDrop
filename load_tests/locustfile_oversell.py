from locust import between, task

from load_tests.locust_base import BaseUser

OVERSELL_PRODUCT_ID = '3fe44185-589a-4703-b640-40df8d7ea67f'


class OversellTestUser(BaseUser):
    """
    High-frequency user targeting the oversell test product.

    Sends rapid reserve requests to exhaust inventory and trigger
    oversell conditions. Use with seed_oversell_product.py to set up
    the test product beforehand.
    """

    wait_time = between(0.1, 0.5)

    @task
    def reserve_oversell_product(self) -> None:
        """
        Reserve the oversell test product.

        Skips if the user is not authenticated.
        """
        if not self.access_token:
            return
        self.do_reserve(OVERSELL_PRODUCT_ID)
