from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel
from sqlalchemy import select

from app.core.audit_log.models import AuditLog
from app.core.audit_log.service import AuditLogService, audit_log_service
from app.services.user.models import User


class MockModel(BaseModel):
    id: str
    email: str
    shipping_address: str
    status: str


@pytest.mark.asyncio
async def test_get_diff_create() -> None:
    new_model = MockModel(
        id='1', email='test@test.com', shipping_address='Street 1', status='active'
    )
    diff = AuditLogService.get_diff(None, new_model)

    assert diff['id'] == [None, '1']
    assert diff['email'] == [None, '[SENSITIVE_DATA_HIDDEN]']
    assert diff['shipping_address'] == [None, '[SENSITIVE_DATA_HIDDEN]']


@pytest.mark.asyncio
async def test_get_diff_delete() -> None:
    old_model = MockModel(
        id='1', email='test@test.com', shipping_address='Street 1', status='active'
    )
    diff = AuditLogService.get_diff(old_model, None)

    assert diff['id'] == ['1', None]
    assert diff['email'] == ['[SENSITIVE_DATA_HIDDEN]', None]
    assert diff['shipping_address'] == ['[SENSITIVE_DATA_HIDDEN]', None]


@pytest.mark.asyncio
async def test_get_diff_update() -> None:
    old_m = MockModel(
        id='1', email='test@test.com', shipping_address='Street 1', status='pending'
    )
    new_m = MockModel(
        id='1', email='test@test.com', shipping_address='Street 2', status='active'
    )

    diff = AuditLogService.get_diff(old_m, new_m)

    assert 'id' not in diff
    assert 'email' not in diff
    assert diff['status'] == ['pending', 'active']
    assert diff['shipping_address'] == [
        '[SENSITIVE_DATA_HIDDEN]',
        '[SENSITIVE_DATA_HIDDEN]',
    ]


@pytest.mark.asyncio
async def test_log_pii_access(db_session: Any) -> None:
    u_id = uuid4()
    actor = User(id=u_id, email=f'actor_{uuid4()}@test.com', password_hash='...')
    db_session.add(actor)
    await db_session.commit()

    target_id = uuid4()

    await audit_log_service.log_pii_access(
        session=db_session,
        actor_id=u_id,
        target_id=target_id,
        target_type='verification_request',
        reason='test_reason',
    )
    await db_session.commit()

    stmt = select(AuditLog).where(AuditLog.target_id == str(target_id))
    result = await db_session.execute(stmt)
    log = result.scalar_one()

    assert log.action == 'pii_access'
    assert str(log.actor_id) == str(u_id)
    assert log.changes['reason'] == 'test_reason'
