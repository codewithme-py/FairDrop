from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import aioboto3  # type: ignore
import structlog
from botocore.exceptions import ClientError

from app.core.config import settings

logger = structlog.get_logger(__name__)

session = aioboto3.Session()


@asynccontextmanager
async def get_s3_client() -> AsyncIterator[Any]:
    async with session.client(
        's3',
        endpoint_url=settings.minio_url,
        region_name='us-east-1',
        aws_access_key_id=settings.minio_root_user,
        aws_secret_access_key=settings.minio_root_password,
        verify=False,
    ) as client:
        yield client


async def init_s3_bucket() -> None:
    async with session.client(
        's3',
        endpoint_url=settings.minio_url,
        region_name='us-east-1',
        aws_access_key_id=settings.minio_root_user,
        aws_secret_access_key=settings.minio_root_password,
        verify=False,
    ) as client:
        try:
            await client.head_bucket(Bucket=settings.minio_bucket_name)
            logger.info(f'Bucket {settings.minio_bucket_name} already exists')
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                await client.make_bucket(Bucket=settings.minio_bucket_name)
                logger.info(f'Bucket {settings.minio_bucket_name} created')
            else:
                logger.error(e)
