from locust import constant_pacing, task

from load_tests.locust_base import BaseUser

TARGET_PRODUCT_ID = '5995fa75-07c7-4b55-82b7-6bfbb52948b8'


class RatelimitUser(BaseUser):
    """
    Rate-limit stress user sending requests at a very high pace.

    Uses constant_pacing of 0.05 seconds to simulate rapid-fire requests
    intended to trigger rate limiting behavior on the server.
    """

    wait_time = constant_pacing(0.05)

    @task
    def spam_profile(self) -> None:
        """
        Send reserve requests as fast as possible to test rate limiting.

        Skips if the user is not authenticated.
        """
        if not self.access_token:
            return
        self.do_reserve(TARGET_PRODUCT_ID)
