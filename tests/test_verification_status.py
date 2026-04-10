import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user.models import VerificationRequest, VerificationStatus


@pytest.mark.asyncio
async def test_get_upgrade_requests(
    async_client: AsyncClient,
    db_session: AsyncSession,
    buyer_headers: dict,
) -> None:
    """
    Verify upgrade request lifecycle: creation, pending status, and rejection.
    with feedback.
    """
    resp = await async_client.post(
        '/api/v1/users/me/upgrade-requests',
        json={'target_role': 'SELLER', 'docs_url': {'id_card': 'url1'}},
        headers=buyer_headers,
    )
    assert resp.status_code == 201
    resp = await async_client.get(
        '/api/v1/users/me/upgrade-requests/latest',
        headers=buyer_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'PENDING'
    assert data['target_role'] == 'SELLER'
    assert data['admin_feedback'] is None
    await db_session.execute(
        update(VerificationRequest).values(
            status=VerificationStatus.REJECTED, admin_feedback='Bad photos'
        )
    )
    await db_session.commit()
    resp = await async_client.get(
        '/api/v1/users/me/upgrade-requests/latest',
        headers=buyer_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'REJECTED'
    assert data['admin_feedback'] == 'Bad photos'
