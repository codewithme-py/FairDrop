from collections import deque
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    CredentialsError,
    InsufficientInventoryError,
    NotFoundError,
    PermissionDeniedError,
    SellerLimitExceededError,
    UserAlreadyExists,
)
from app.services.inventory.models import Product, ProductStatus, Reservation
from app.services.inventory.schemas import (
    ProductCreate,
    ProductUpdate,
    ReservationCreate,
)
from app.services.inventory.service import InventoryAdminService, InventoryService
from app.services.orders.models import Order, OrderStatus
from app.services.orders.schemas import OrderCreate
from app.services.orders.service import OrderService
from app.services.user.models import (
    APIKeyB2BPartner,
    RefreshToken,
    User,
    UserRole,
)
from app.services.user.schemas import UserCreate
from app.services.user.service import UserService


class DeterministicMockSession:
    """Deterministic mock session with predefined responses and integrity errors."""

    def __init__(self, responses: Any = None, raise_integrity: bool = False) -> None:
        self.responses = deque(responses or [])
        self.raise_integrity = raise_integrity
        self.added_objs: list[Any] = []
        self.deleted_objs: list[Any] = []

    def add(self, obj: Any) -> None:
        self.added_objs.append(obj)

    async def flush(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def delete(self, obj: Any) -> None:
        self.deleted_objs.append(obj)

    async def commit(self) -> None:
        if self.raise_integrity:
            raise IntegrityError(None, None, Exception())

    async def execute(self, stmt: Any) -> Any:
        res_obj = self.responses.popleft() if self.responses else None
        res = MagicMock()
        res.unique.return_value = res
        res.scalars.return_value = res
        res.scalar_one_or_none.return_value = res_obj
        res.scalar_one.return_value = res_obj
        res.scalar.return_value = res_obj
        res.all.return_value = (
            res_obj if isinstance(res_obj, list) else [res_obj] if res_obj else []
        )
        res.with_for_update.return_value = res
        return res

    async def refresh(self, obj: Any, **kwargs: Any) -> None:
        if not getattr(obj, 'id', None):
            obj.id = uuid4()
        if not getattr(obj, 'created_at', None):
            obj.created_at = datetime.now(UTC)
        if not getattr(obj, 'updated_at', None):
            obj.updated_at = datetime.now(UTC)
        if hasattr(obj, 'items') and not getattr(obj, 'items', None):
            obj.items = []


def get_p(u_id: Any) -> Product:
    """Create a draft product for the given user ID in industrial tests."""
    return Product(
        id=uuid4(),
        owner_id=u_id,
        price=Decimal('10.0'),
        name='n',
        status=ProductStatus.DRAFT,
        qty_available=5,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_inventory_industrial_GIGA() -> None:
    """Inventory test: CRUD, moderation, reservation, and limits."""
    u_id = uuid4()
    seller = User(id=u_id, role=UserRole.SELLER, is_verified=True)
    admin = User(id=uuid4(), role=UserRole.ADMIN)
    p = get_p(u_id)
    with (
        patch('app.services.inventory.service.audit_log_service', AsyncMock()),
        patch(
            'app.services.inventory.service.ProductRead.model_validate',
            return_value=MagicMock(),
        ),
    ):
        await InventoryService.create_product(
            cast(AsyncSession, DeterministicMockSession([None])),
            u_id,
            ProductCreate(name='n', price=Decimal('10'), qty_available=5),
            seller,
        )
        await InventoryService.get_product(
            cast(AsyncSession, DeterministicMockSession([p])), p.id
        )
        await InventoryService.get_products(
            cast(AsyncSession, DeterministicMockSession([[p]])),
            status=ProductStatus.ACTIVE,
        )
        await InventoryService.update_product(
            cast(AsyncSession, DeterministicMockSession([p])),
            p.id,
            ProductUpdate(name='new'),
            seller,
        )
        await InventoryService.delete_product(
            cast(AsyncSession, DeterministicMockSession([p])),
            p.id,
            seller,
        )
        await InventoryService.reserve_items(
            cast(AsyncSession, DeterministicMockSession([p])),
            u_id,
            'k',
            ReservationCreate(product_id=p.id, quantity=1),
        )
        await InventoryService.create_product(
            cast(AsyncSession, DeterministicMockSession([])),
            admin.id,
            ProductCreate(name='n', price=Decimal('10'), qty_available=5),
            admin,
        )
        with pytest.raises(SellerLimitExceededError):
            await InventoryService.create_product(
                cast(AsyncSession, DeterministicMockSession([[p] * 100])),
                u_id,
                ProductCreate(name='n', price=Decimal('10'), qty_available=5),
                seller,
            )
        await InventoryService.submit_for_moderation(
            cast(AsyncSession, DeterministicMockSession([p])), p.id, seller
        )
        await InventoryAdminService.claim_for_moderation(
            cast(AsyncSession, DeterministicMockSession([p])), p.id, admin
        )
        p.status = ProductStatus.MODERATION_IN_PROGRESS
        await InventoryAdminService.approve_product(
            cast(AsyncSession, DeterministicMockSession([p])), p.id, admin
        )
        p.status = ProductStatus.MODERATION_IN_PROGRESS
        await InventoryAdminService.reject_product(
            cast(AsyncSession, DeterministicMockSession([p])), p.id, admin, 'bad'
        )
        await InventoryAdminService.change_status(
            cast(AsyncSession, DeterministicMockSession([p])),
            p.id,
            ProductStatus.ACTIVE,
            admin,
        )
        with pytest.raises(NotFoundError):
            await InventoryService.get_product(
                cast(AsyncSession, DeterministicMockSession([None])), uuid4()
            )
        with pytest.raises(InsufficientInventoryError):
            await InventoryService.reserve_items(
                cast(AsyncSession, DeterministicMockSession([p])),
                u_id,
                'k',
                ReservationCreate(product_id=p.id, quantity=100),
            )
        with pytest.raises(ConflictError):
            await InventoryService.reserve_items(
                cast(AsyncSession, DeterministicMockSession([p], raise_integrity=True)),
                u_id,
                'k',
                ReservationCreate(product_id=p.id, quantity=1),
            )


@pytest.mark.asyncio
async def test_orders_industrial_GIGA() -> None:
    """Order test: creation, payment, cancellation, and admin access."""
    u_id, p_id = uuid4(), uuid4()
    usr = User(id=u_id)
    p = get_p(u_id)
    p.id = p_id
    res = Reservation(
        id=uuid4(),
        user_id=u_id,
        product_id=p_id,
        qty_reserved=2,
        status=OrderStatus.PENDING,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    ord_obj = Order(
        id=uuid4(),
        user_id=u_id,
        status=OrderStatus.PENDING,
        total_amount=Decimal('20.0'),
        items=[],
        created_at=datetime.now(UTC),
    )
    with (
        patch('app.services.orders.service.audit_log_service', AsyncMock()),
        patch(
            'app.services.orders.service.OrderResponse.model_validate',
            return_value=MagicMock(),
        ),
    ):
        await OrderService.create_order_from_reservation(
            cast(AsyncSession, DeterministicMockSession([res, p])),
            usr,
            OrderCreate(reservation_id=res.id),
        )
        await OrderService.get_order_for_details(
            cast(AsyncSession, DeterministicMockSession([ord_obj])), ord_obj.id, usr
        )
        with patch(
            'app.services.orders.service.mark_reservation_by_order_as_completed',
            AsyncMock(),
        ):
            await OrderService.confirm_order_payment(
                cast(AsyncSession, DeterministicMockSession([ord_obj])), ord_obj.id, usr
            )
            ord_obj.status = OrderStatus.PENDING
        with patch(
            'app.services.orders.service.cancel_reservation_by_order_and_return_stock',
            AsyncMock(),
        ):
            await OrderService.cancel_order(
                cast(AsyncSession, DeterministicMockSession([ord_obj])), ord_obj.id, usr
            )
        adm = User(id=uuid4(), role=UserRole.ADMIN)
        await OrderService.get_order_for_details(
            cast(AsyncSession, DeterministicMockSession([ord_obj])), ord_obj.id, adm
        )
        with pytest.raises(NotFoundError):
            await OrderService.create_order_from_reservation(
                cast(AsyncSession, DeterministicMockSession([None])),
                usr,
                OrderCreate(reservation_id=uuid4()),
            )


@pytest.mark.asyncio
async def test_user_industrial_GIGA() -> None:
    """Comprehensive user test covering registration, auth, tokens, and API keys."""
    u_id = uuid4()
    usr = User(id=u_id, email='u@t.com', password_hash='h')
    tok = RefreshToken(user=usr, expires_at=datetime.utcnow() + timedelta(days=1))
    key = APIKeyB2BPartner(
        id=uuid4(), user_id=u_id, hashed_key='h', key_prefix='p', is_active=True
    )
    with (
        patch('app.core.hashing.pwd_context.hash', return_value='h'),
        patch('app.core.hashing.pwd_context.verify', return_value=True),
    ):
        await UserService.create_user(
            cast(AsyncSession, DeterministicMockSession([None])),
            UserCreate(email='u' + str(uuid4()) + '@t.com', password='p'),
        )
        await UserService.authenticate_user(
            cast(AsyncSession, DeterministicMockSession([usr])), 'u@t.com', 'p'
        )
        await UserService.create_refresh_token(
            cast(AsyncSession, DeterministicMockSession([])), u_id
        )
        await UserService.refresh_access_token(
            cast(AsyncSession, DeterministicMockSession([tok])), 't'
        )
        await UserService.create_api_key_b2b_partner(
            cast(AsyncSession, DeterministicMockSession([])),
            u_id,
            'n',
        )
        await UserService.authenticate_api_key_b2b_partner(
            cast(AsyncSession, DeterministicMockSession([key])), 'k'
        )
        await UserService.delete_api_key_b2b_partner(
            cast(AsyncSession, DeterministicMockSession([key])), u_id, key.id
        )
        await UserService.create_verification_request(
            cast(AsyncSession, DeterministicMockSession([None])), u_id, UserRole.SELLER
        )
        with pytest.raises(UserAlreadyExists):
            await UserService.create_user(
                cast(AsyncSession, DeterministicMockSession([usr])),
                UserCreate(email='u@t.com', password='p'),
            )
        tok.expires_at = datetime.utcnow() - timedelta(1)
        with pytest.raises(CredentialsError):
            await UserService.refresh_access_token(
                cast(AsyncSession, DeterministicMockSession([tok])), 't'
            )
        with pytest.raises(PermissionDeniedError):
            await UserService.create_verification_request(
                cast(AsyncSession, DeterministicMockSession([None])),
                u_id,
                UserRole.ADMIN,
            )
