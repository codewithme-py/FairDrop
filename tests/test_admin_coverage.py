from http import HTTPStatus
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.hashing import get_password_hash_sync
from app.services.user.models import (
    User,
    UserRole,
    VerificationRequest,
    VerificationStatus,
)


@pytest.mark.asyncio
async def test_admin_login_and_logout(
    async_client: AsyncClient, db_session: Any
) -> None:
    """Verify admin login renders the panel and logout returns to login page."""
    password = 'admin_password'
    admin_user = User(
        email=f'admin_{uuid4().hex[:4]}@test.com',
        password_hash=get_password_hash_sync(password),
        role=UserRole.ADMIN,
        is_verified=True,
    )
    db_session.add(admin_user)
    await db_session.commit()

    resp = await async_client.post(
        '/admin/login',
        data={'username': admin_user.email, 'password': password},
        follow_redirects=True,
    )
    assert resp.status_code == HTTPStatus.OK
    assert 'FairDrop' in resp.text
    resp = await async_client.get('/admin/logout', follow_redirects=True)
    assert 'Login' in resp.text


@pytest.mark.asyncio
async def test_verification_approval_on_model_change(
    async_client: AsyncClient, db_session: Any
) -> None:
    """Verify admin can approve a verification request and update user role."""
    admin_pass = 'admin_pass'
    admin = User(
        email=f'adm_{uuid4().hex[:4]}@test.com',
        password_hash=get_password_hash_sync(admin_pass),
        role=UserRole.ADMIN,
        is_verified=True,
    )
    target_user = User(
        email=f'user_{uuid4().hex[:4]}@test.com',
        password_hash='...',
        role=UserRole.USER,
        is_verified=False,
    )
    db_session.add_all([admin, target_user])
    await db_session.commit()
    await db_session.refresh(target_user)
    v_req = VerificationRequest(
        user_id=target_user.id,
        target_role=UserRole.SELLER,
        status=VerificationStatus.PENDING,
    )
    db_session.add(v_req)
    await db_session.commit()
    await db_session.refresh(v_req)
    await async_client.post(
        '/admin/login',
        data={'username': admin.email, 'password': admin_pass},
        follow_redirects=True,
    )
    resp = await async_client.post(
        f'/admin/verification-request/edit/{v_req.id}',
        data={'status': 'APPROVED', 'admin_feedback': 'Approved!'},
        follow_redirects=False,
    )
    assert resp.status_code in (HTTPStatus.FOUND, HTTPStatus.SEE_OTHER, HTTPStatus.OK)
    await db_session.refresh(target_user)
    assert target_user.is_verified is True
    assert target_user.role == UserRole.SELLER


@pytest.mark.asyncio
async def test_moderator_rbac_enforcement(
    async_client: AsyncClient, db_session: Any
) -> None:
    """Verify moderators are denied access to admin user edit endpoints."""
    mod_pass = 'mod_pass'
    moderator = User(
        email=f'mod_{uuid4().hex[:4]}@test.com',
        password_hash=get_password_hash_sync(mod_pass),
        role=UserRole.MODERATOR,
        is_verified=True,
    )
    target_user = User(
        email=f'victim_{uuid4().hex[:4]}@test.com',
        password_hash='...',
        role=UserRole.USER,
    )
    db_session.add_all([moderator, target_user])
    await db_session.commit()
    await async_client.post(
        '/admin/login',
        data={'username': moderator.email, 'password': mod_pass},
        follow_redirects=True,
    )
    resp = await async_client.get(
        f'/admin/user/edit/{target_user.id}', follow_redirects=False
    )
    assert resp.status_code in (HTTPStatus.FORBIDDEN, HTTPStatus.SEE_OTHER)


@pytest.mark.asyncio
async def test_admin_formatters_rendering(
    async_client: AsyncClient, db_session: Any
) -> None:
    """Verify admin panel formatter pages render correctly."""
    admin_pass = 'admin_pass'
    admin = User(
        email=f'adm_f_{uuid4().hex[:4]}@test.com',
        password_hash=get_password_hash_sync(admin_pass),
        role=UserRole.ADMIN,
        is_verified=True,
    )
    db_session.add(admin)
    await db_session.commit()
    await async_client.post(
        '/admin/login',
        data={'username': admin.email, 'password': admin_pass},
        follow_redirects=True,
    )
    resp = await async_client.get('/admin/verification-request/list')
    assert resp.status_code == HTTPStatus.OK
    assert 'Verification' in resp.text
