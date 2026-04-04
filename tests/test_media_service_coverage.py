from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from app.services.inventory.models import Product
from app.services.media.models import ImageStatus, ProductImage
from app.services.media.schemas import MinioWebhookEvent
from app.services.media.service import (
    get_secure_file_path,
    handle_minio_webhook,
    sanitize_image_metadata,
)
from app.services.user.models import User, UserRole


@pytest.fixture
async def sample_buyer(db_session: Any) -> Any:
    u = User(
        id=uuid4(),
        email=f'buyer_{uuid4().hex[:4]}@mail.com',
        password_hash='h',
        role=UserRole.USER,
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest.fixture
async def sample_product(db_session: Any, sample_buyer: Any) -> Any:
    p = Product(
        id=uuid4(),
        owner_id=sample_buyer.id,
        name='Test',
        price=Decimal('10'),
        qty_available=10,
        status='ACTIVE',
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


@pytest.mark.asyncio
async def test_get_secure_file_path_not_found(db_session: Any) -> None:
    # Invalid target_type
    assert await get_secure_file_path(db_session, 'unknown_type', uuid4()) is None
    # Valid target_type, but fake ID
    assert await get_secure_file_path(db_session, 'product_image', uuid4()) is None


@pytest.mark.asyncio
async def test_sanitize_image_metadata() -> None:
    # It just passes, calling it for coverage
    await sanitize_image_metadata(None, 'bucket', 'key')


@pytest.mark.asyncio
async def test_handle_minio_webhook_no_records(db_session: Any) -> None:
    event = MinioWebhookEvent.model_validate({'Records': []})
    await handle_minio_webhook(db_session, event)


@pytest.mark.asyncio
async def test_handle_minio_webhook_not_created(db_session: Any) -> None:
    record = {
        'eventName': 's3:ObjectRemoved:Delete',
        's3': {'object': {'key': 'test.jpg'}},
    }
    event = MinioWebhookEvent.model_validate({'Records': [record]})
    await handle_minio_webhook(db_session, event)


@pytest.mark.asyncio
async def test_handle_minio_webhook_image_not_found(db_session: Any) -> None:
    record = {
        'eventName': 's3:ObjectCreated:Put',
        's3': {'object': {'key': 'phantom/test.jpg'}},
    }
    event = MinioWebhookEvent.model_validate({'Records': [record]})
    await handle_minio_webhook(db_session, event)


@pytest.mark.asyncio
async def test_handle_minio_webhook_missing_arq(
    db_session: Any, sample_product: Any
) -> None:
    unique_path = f'missing_arq_{uuid4().hex}/test.jpg'
    # Need a valid image in pending state
    img = ProductImage(
        id=uuid4(),
        product_id=sample_product.id,
        file_path=unique_path,
        status=ImageStatus.PENDING,
    )
    db_session.add(img)
    await db_session.commit()

    record = {
        'eventName': 's3:ObjectCreated:Put',
        's3': {'object': {'key': unique_path}},
    }
    event = MinioWebhookEvent.model_validate({'Records': [record]})

    # Missing arq_redis
    await handle_minio_webhook(db_session, event, arq_redis=None)


@pytest.mark.asyncio
async def test_generate_presigned_get_url() -> None:
    from unittest.mock import AsyncMock

    s3 = AsyncMock()
    s3.generate_presigned_url.return_value = 'http://presigned'
    from app.services.media.service import generate_presigned_get_url

    assert await generate_presigned_get_url(s3, 'test.jpg') == 'http://presigned'


@pytest.mark.asyncio
async def test_get_secure_file_path_verification(
    db_session: Any, sample_buyer: Any
) -> None:
    from app.services.user.models import (
        UserRole,
        VerificationRequest,
        VerificationStatus,
    )

    v_req = VerificationRequest(
        id=uuid4(),
        user_id=sample_buyer.id,
        target_role=UserRole.SELLER,
        status=VerificationStatus.PENDING,
        docs_url={'doc1': 's3://bucket/doc1.pdf'},
    )
    db_session.add(v_req)
    await db_session.commit()
    assert (
        await get_secure_file_path(db_session, 'verification_doc', v_req.id, 'doc1')
        == 's3://bucket/doc1.pdf'
    )
    assert (
        await get_secure_file_path(
            db_session, 'verification_doc', v_req.id, 'doc_not_exist'
        )
        is None
    )


@pytest.mark.asyncio
async def test_get_secure_file_path_product_image_success(
    db_session: Any, sample_product: Any
) -> None:
    img = ProductImage(
        id=uuid4(),
        product_id=sample_product.id,
        file_path='exists.jpg',
        status=ImageStatus.ACTIVE,
    )
    db_session.add(img)
    await db_session.commit()
    assert (
        await get_secure_file_path(db_session, 'product_image', img.id) == 'exists.jpg'
    )


@pytest.mark.asyncio
async def test_generate_upload_url(db_session: Any, sample_product: Any) -> None:
    from unittest.mock import AsyncMock

    from app.services.media.schemas import ImageUploadRequest

    s3 = AsyncMock()
    s3.generate_presigned_post.return_value = {'url': 'http://up', 'fields': {}}
    from app.services.media.service import generate_upload_url

    req = ImageUploadRequest(filename='test.jpg', content_type='image/jpeg')
    res = await generate_upload_url(db_session, s3, sample_product.id, req)
    assert res.url == 'http://up'


@pytest.mark.asyncio
async def test_handle_minio_webhook_success_and_not_pending(
    db_session: Any, sample_product: Any
) -> None:
    from unittest.mock import AsyncMock

    unique_path1 = f'arq_{uuid4().hex}/test1.jpg'
    unique_path2 = f'arq_{uuid4().hex}/test2.jpg'

    img1 = ProductImage(
        id=uuid4(),
        product_id=sample_product.id,
        file_path=unique_path1,
        status=ImageStatus.PENDING,
    )
    img2 = ProductImage(
        id=uuid4(),
        product_id=sample_product.id,
        file_path=unique_path2,
        status=ImageStatus.ACTIVE,
    )

    db_session.add_all([img1, img2])
    await db_session.commit()

    record1 = {
        'eventName': 's3:ObjectCreated:Put',
        's3': {'object': {'key': unique_path1}},
    }
    record2 = {
        'eventName': 's3:ObjectCreated:Put',
        's3': {'object': {'key': unique_path2}},
    }

    event = MinioWebhookEvent.model_validate({'Records': [record1, record2]})
    redis_mock = AsyncMock()
    await handle_minio_webhook(db_session, event, arq_redis=redis_mock)

    # Should enqueue img1, but skip img2
    assert redis_mock.enqueue_job.call_count == 1
