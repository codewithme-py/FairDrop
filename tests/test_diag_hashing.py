from typing import Any
from uuid import uuid4

import pytest

from app.core.hashing import get_password_hash
from app.services.user.models import APIKeyB2BPartner, User, UserRole


@pytest.mark.asyncio
async def test_diagnostic_hashing_and_db(db_session: Any) -> None:
    """Verify password hashing produces valid, storable output."""
    user = User(
        id=uuid4(),
        email=f'diag_{uuid4().hex[:4]}@mail.com',
        password_hash='...',
        role=UserRole.USER,
    )
    db_session.add(user)
    await db_session.commit()
    raw_key = 'abcde-1234567890-test-key'
    hashed_key = await get_password_hash(raw_key)
    print(f'DIAG DEBUG: hashed_key={hashed_key!r}')
    assert hashed_key is not None
    assert len(hashed_key) > 10
    api_key_obj = APIKeyB2BPartner(
        user_id=user.id, name='Diag Key', key_prefix=raw_key[:5], hashed_key=hashed_key
    )
    db_session.add(api_key_obj)
    await db_session.commit()
    await db_session.refresh(api_key_obj)

    assert api_key_obj.hashed_key == hashed_key
    print('DIAG SUCCESS: Item created in DB')
