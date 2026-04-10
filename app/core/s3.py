from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import aioboto3  # type: ignore
import structlog
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings

logger = structlog.get_logger(__name__)

session = aioboto3.Session()
s3_config = Config(s3={'addressing_style': 'path'})


async def get_s3_client_gen() -> AsyncIterator[Any]:
    """
    Async context manager that yields an S3 client configured for MinIO.

    Yields:
        An aioboto3 S3 client instance configured to connect to the MinIO endpoint.
    """
    async with session.client(
        's3',
        endpoint_url=settings.minio_url,
        region_name='us-east-1',
        aws_access_key_id=settings.minio_root_user,
        aws_secret_access_key=settings.minio_root_password,
        verify=False,
        config=s3_config,
    ) as client:
        yield client


get_s3_client = asynccontextmanager(get_s3_client_gen)


async def init_s3_bucket() -> None:
    """
    Ensure the configured MinIO bucket exists, creating it if necessary.

    Checks for the bucket using head_bucket and creates it with
    create_bucket if a 404 is returned.
    """
    async with session.client(
        's3',
        endpoint_url=settings.minio_url,
        region_name='us-east-1',
        aws_access_key_id=settings.minio_root_user,
        aws_secret_access_key=settings.minio_root_password,
        verify=False,
        config=s3_config,
    ) as client:
        try:
            await client.head_bucket(Bucket=settings.minio_bucket_name)
            logger.info(f'Bucket {settings.minio_bucket_name} already exists')
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                await client.create_bucket(Bucket=settings.minio_bucket_name)
                logger.info(f'Bucket {settings.minio_bucket_name} created')
            else:
                logger.error(e)
