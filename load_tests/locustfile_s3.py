from locust import between, task

from load_tests.locust_base import BaseUser

TARGET_PRODUCT_ID = '5995fa75-07c7-4b55-82b7-6bfbb52948b8'


class PreSignedUrlForS3User(BaseUser):
    wait_time = between(1.0, 3.0)

    @task
    def get_presigned_url(self) -> None:
        self.do_get_presigned_url(TARGET_PRODUCT_ID, 'test.jpg', 'image/jpeg')
