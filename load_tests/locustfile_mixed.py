from locust import between, task

from load_tests.locust_base import BaseUser

TARGET_PRODUCT_ID = '5995fa75-07c7-4b55-82b7-6bfbb52948b8'


class MixedLoadUser(BaseUser):
    """
    Mixed workload user simulating realistic traffic patterns.

    Exercises a blend of reserve, profile view, and token refresh tasks
    weighted 6:2:2 to approximate a typical user session distribution.
    """

    wait_time = between(1.0, 3.0)

    @task(6)
    def reserve_product(self) -> None:
        """
        Reserve a unit of the target product.

        Skips if the user is not authenticated.
        """
        if not self.access_token:
            return
        self.do_reserve(TARGET_PRODUCT_ID)

    @task(2)
    def view_profile(self) -> None:
        """
        Fetch the current user's profile.

        Skips if the user is not authenticated.
        """
        if not self.access_token:
            return
        self.do_view_profile()

    @task(2)
    def update_token(self) -> None:
        """
        Refresh the access token using the refresh token.

        Skips if no refresh token is available.
        """
        if not self.refresh_token:
            return
        self.do_refresh_token()
