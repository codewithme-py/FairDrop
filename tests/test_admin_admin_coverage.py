from typing import Any
from unittest.mock import MagicMock

import pytest

from app.core.admin.admin import (
    AdminAccessMixin,
    AdminPanelFormatter,
    UserAdmin,
)
from app.services.user.models import UserRole


@pytest.fixture
def mock_request() -> Any:
    req = MagicMock()
    req.state.user = MagicMock()
    req.state.user.role = UserRole.ADMIN
    return req


def test_admin_access_mixin(mock_request: Any) -> None:
    # Test ADMIN
    instance = MagicMock(spec=AdminAccessMixin)
    assert AdminAccessMixin.is_accessible(instance, mock_request) is True
    assert AdminAccessMixin.is_visible(instance, mock_request) is True

    # Test No User
    req_no_usr = MagicMock()
    req_no_usr.state.user = None
    assert AdminAccessMixin.is_accessible(instance, req_no_usr) is False
    assert AdminAccessMixin.is_visible(instance, req_no_usr) is False


def test_admin_panel_formatter() -> None:
    class DummyModel:
        status = 'ACTIVE'
        user_id = '123'
        product_id = '456'
        order_id = '789'
        docs_url = {'doc1': 'url1'}
        other = 'test'

        def __getattr__(self, name: str) -> Any:
            return None

    model = DummyModel()

    # Status formatter
    assert 'ACTIVE' in AdminPanelFormatter.status_formatter(model, 'status')
    assert AdminPanelFormatter.status_formatter(model, 'other') == 'test'

    # Links
    assert '123' in AdminPanelFormatter.user_link_formatter(model, 'user_id')
    assert AdminPanelFormatter.user_link_formatter(model, 'nonexistent') == 'N/A'

    assert '456' in AdminPanelFormatter.product_link_formatter(model, 'product_id')
    assert '789' in AdminPanelFormatter.order_link_formatter(model, 'order_id')

    # Docs
    assert 'doc1' in AdminPanelFormatter.docs_link_formatter(model, 'docs_url')

    class DummyNoDocs:
        def __getattr__(self, name: str) -> Any:
            return None

    assert (
        AdminPanelFormatter.docs_link_formatter(DummyNoDocs(), 'docs_url') == 'No docs'
    )


def test_user_admin_accessible(mock_request: Any) -> None:
    instance = MagicMock(spec=UserAdmin)
    assert UserAdmin.is_accessible(instance, mock_request) is True

    req_no = MagicMock()
    req_no.state.user = None
    assert UserAdmin.is_accessible(instance, req_no) is False

    req_mod = MagicMock()
    req_mod.state.user = MagicMock()
    req_mod.state.user.role = UserRole.MODERATOR
    req_mod.scope = {
        'endpoint': MagicMock(__name__='create'),
        'route': MagicMock(name='create'),
    }
    req_mod.url.path = '/create/'

    assert UserAdmin.is_accessible(instance, req_mod) is False

    # Allowed moderator path
    req_mod_ok = MagicMock()
    req_mod_ok.state.user = MagicMock()
    req_mod_ok.state.user.role = UserRole.MODERATOR
    req_mod_ok.scope = {
        'endpoint': MagicMock(__name__='view'),
        'route': MagicMock(name='view'),
    }
    req_mod_ok.url.path = '/view/'
    assert UserAdmin.is_accessible(instance, req_mod_ok) is True


@pytest.mark.asyncio
async def test_verification_admin_model_change() -> None:
    # mock everything or just pass for now
    pass
