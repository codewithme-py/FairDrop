from typing import Any

from markupsafe import Markup
from sqladmin import ModelView
from sqlalchemy import select
from starlette.requests import Request

from app.core.audit_log.models import AuditLog
from app.core.database import async_session_factory
from app.services.inventory.models import Product, Reservation
from app.services.orders.models import Order
from app.services.user.models import (
    APIKeyB2BPartner,
    User,
    UserRole,
    VerificationRequest,
    VerificationStatus,
)


class AdminAccessMixin(ModelView):
    """
    Mixin that restricts access to admin model views to ADMIN users only.

    Provides ``is_accessible`` and ``is_visible`` checks that ensure only
    users with the ``ADMIN`` role can view and interact with the model
    in the SQLAdmin panel.
    """

    def is_accessible(self, request: Request) -> bool:
        """
        Check whether the current user has ADMIN role for access control.

        Args:
            request: The incoming HTTP request with user information attached
                to ``request.state``.

        Returns:
            ``True`` if the authenticated user has the ``ADMIN`` role;
            ``False`` otherwise.
        """
        user = getattr(request.state, 'user', None)
        return user is not None and user.role == UserRole.ADMIN

    def is_visible(self, request: Request) -> bool:
        """
        Check whether the current user has ADMIN role for menu visibility.

        Args:
            request: The incoming HTTP request with user information attached
                to ``request.state``.

        Returns:
            ``True`` if the authenticated user has the ``ADMIN`` role;
            ``False`` otherwise.
        """
        user = getattr(request.state, 'user', None)
        return user is not None and user.role == UserRole.ADMIN


class AdminPanelFormatter:
    """
    Utility class providing formatter methods for displaying data in the admin panel.

    Each static method produces HTML markup (via ``Markup``) suitable for
    use as a SQLAdmin column formatter, rendering badges, links, and
    styled status indicators.
    """

    @staticmethod
    def status_formatter(model: Any, name: Any) -> Any:
        """
        Render a status field value as a colored Bootstrap badge.

        Maps common status and role values to appropriate Bootstrap badge
        colors (e.g., ``ACTIVE`` to green, ``CANCELLED`` to red).

        Args:
            model: The SQLAlchemy model instance being formatted.
            name: The attribute name to read from the model (e.g., ``status``,
                ``role``, ``target_role``).

        Returns:
            A ``Markup`` string containing the HTML badge, or the raw
            attribute value if the name is not a recognized status field.
        """
        status_colors = {
            'ACTIVE': 'success',
            'PENDING': 'warning',
            'REJECTED': 'danger',
            'PENDING_MODERATION': 'info',
            'PAID': 'success',
            'SHIPPED': 'info',
            'COMPLETED': 'success',
            'CANCELLED': 'danger',
            'FAILED': 'danger',
            'EXPIRED': 'secondary',
            'DRAFT': 'secondary',
            'MODERATION_IN_PROGRESS': 'info',
            'APPROVED': 'success',
            'SELLER_B2B': 'primary',
            'USER_B2B': 'secondary',
        }
        if name in ('status', 'target_role', 'role'):
            value = getattr(model, name)
            color = status_colors.get(value, 'secondary')
            return Markup(f'<span class="badge bg-{color}">{value}</span>')
        return getattr(model, name)

    @staticmethod
    def user_link_formatter(model: Any, name: Any) -> Any:
        """
        Render a user ID as a clickable link to the user detail page.

        Args:
            model: The SQLAlchemy model instance being formatted.
            name: The attribute name holding the user ID.

        Returns:
            A ``Markup`` anchor tag linking to ``/admin/user/details/<id>``,
            or ``'N/A'`` if the user ID is empty.
        """
        user_id = getattr(model, name)
        if not user_id:
            return 'N/A'
        return Markup(f'<a href="/admin/user/details/{user_id}">{user_id}</a>')

    @staticmethod
    def product_link_formatter(model: Any, name: Any) -> Any:
        """
        Render a product ID as a clickable link to the product detail page.

        Args:
            model: The SQLAlchemy model instance being formatted.
            name: The attribute name holding the product ID.

        Returns:
            A ``Markup`` anchor tag linking to ``/admin/product/details/<id>``,
            or ``'N/A'`` if the product ID is empty.
        """
        product_id = getattr(model, name)
        if not product_id:
            return 'N/A'
        return Markup(f'<a href="/admin/product/details/{product_id}">{product_id}</a>')

    @staticmethod
    def order_link_formatter(model: Any, name: Any) -> Any:
        """
        Render an order ID as a clickable link to the order detail page.

        Args:
            model: The SQLAlchemy model instance being formatted.
            name: The attribute name holding the order ID.

        Returns:
            A ``Markup`` anchor tag linking to ``/admin/order/details/<id>``,
            or ``'N/A'`` if the order ID is empty.
        """
        order_id = getattr(model, name)
        if not order_id:
            return 'N/A'
        return Markup(f'<a href="/admin/order/details/{order_id}">{order_id}</a>')

    @staticmethod
    def docs_link_formatter(model: Any, name: Any) -> Any:
        """
        Render verification document keys as clickable links for viewing.

        Generates a comma-separated list of anchor tags, each linking to
        a verification document endpoint keyed by document type.

        Args:
            model: The SQLAlchemy model instance being formatted (must have
                an ``id`` attribute).
            name: The attribute name holding the document data as a dict
                mapping document types to URLs or values.

        Returns:
            A ``Markup`` string of comma-separated links, or ``'No docs'``
            if the document data is empty.
        """
        docs = getattr(model, name)
        if not docs:
            return 'No docs'
        links = []
        if isinstance(docs, dict):
            for doc_type in docs.keys():
                links.append(
                    f'<a href="/api/v1/media/view/verification_doc/{model.id}'
                    f'?doc_key={doc_type}" target="_blank">{doc_type}</a>'
                )
        return Markup(', '.join(links))


class VerificationRequestAdmin(AdminAccessMixin, model=VerificationRequest):
    """
    Admin panel view for managing user verification requests.

    Allows admins with ``ADMIN`` role to view, approve, or reject user
    verification requests. Approving a request automatically upgrades
    the user's role to the requested target role.
    """

    column_list = [
        VerificationRequest.id,
        VerificationRequest.user_id,
        VerificationRequest.target_role,
        VerificationRequest.status,
        VerificationRequest.docs_url,
        VerificationRequest.admin_feedback,
        VerificationRequest.created_at,
        VerificationRequest.updated_at,
    ]
    column_searchable_list = column_list
    column_default_sort = [('created_at', True)]
    column_formatters = {
        'user_id': AdminPanelFormatter.user_link_formatter,
        'target_role': AdminPanelFormatter.status_formatter,
        'status': AdminPanelFormatter.status_formatter,
        'docs_url': AdminPanelFormatter.docs_link_formatter,
    }
    column_formatters_detail = column_formatters
    name = 'Verification Request'
    name_plural = 'Verification Requests'
    icon = 'fa-solid fa-user-check'
    can_delete = False
    can_create = False
    can_edit = True
    form_columns = [VerificationRequest.status, VerificationRequest.admin_feedback]

    async def on_model_change(
        self, data: dict, model: Any, is_created: bool, request: Request
    ) -> None:
        """
        Handle post-save logic for verification request updates.

        When a verification request status is changed to ``APPROVED``, this
        hook automatically updates the associated user's role to the
        requested target role and marks the user as verified.

        Args:
            data: Dictionary of form field values being saved.
            model: The ``VerificationRequest`` model instance being updated.
            is_created: ``True`` if this is a new record creation; ``False``
                for updates.
            request: The incoming HTTP request.
        """
        if not is_created and data.get('status') == VerificationStatus.APPROVED:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(User).where(User.id == model.user_id)
                )
                user = result.scalar_one()
                user.role = model.target_role
                user.is_verified = True
                await session.commit()


class UserAdmin(ModelView, model=User):
    """
    Admin panel view for managing user accounts.

    Supports both ``ADMIN`` and ``MODERATOR`` roles. Moderators can view
    users but cannot create, edit, or delete records.
    """

    column_list = [User.id, User.email, User.role, User.is_active]
    column_searchable_list = [User.id, User.email]
    can_delete = False
    name = 'User'
    name_plural = 'Users'
    icon = 'fa-solid fa-user'
    column_default_sort = [('created_at', True)]

    def is_accessible(self, request: Request) -> bool:
        """
        Check whether the requesting user can access this admin view.

        Allows both ``ADMIN`` and ``MODERATOR`` roles. Moderators are
        restricted from create, edit, and delete operations.

        Args:
            request: The incoming HTTP request with user information and
                route details.

        Returns:
            ``True`` if the user has an allowed role and the requested
                operation is permitted; ``False`` otherwise.
        """
        user = getattr(request.state, 'user', None)
        if not user:
            return False

        if user.role == UserRole.MODERATOR:
            endpoint = request.scope.get('endpoint')
            endpoint_name = getattr(endpoint, '__name__', '')
            route = request.scope.get('route')
            route_name = getattr(route, 'name', '')
            path = request.url.path
            forbidden = {'create', 'edit', 'delete'}
            if (
                endpoint_name in forbidden
                or route_name in forbidden
                or any(f'/{x}/' in path for x in forbidden)
            ):
                return False
        return user.role in (UserRole.ADMIN, UserRole.MODERATOR)


class ProductAdmin(ModelView, model=Product):
    """
    Admin panel view for managing product listings.

    Allows admins to view product details, update moderation status,
    assign moderators, and add moderation comments. Creation and
    deletion are disabled.
    """

    column_list = [
        Product.id,
        Product.name,
        Product.price,
        Product.qty_available,
        Product.status,
        Product.owner_id,
        Product.moderator_id,
        Product.moderation_comment,
    ]
    column_labels = {'qty_available': 'Quantity Available'}
    column_default_sort = [('created_at', True)]
    column_formatters = {
        'status': AdminPanelFormatter.status_formatter,
        'owner_id': AdminPanelFormatter.user_link_formatter,
        'moderator_id': AdminPanelFormatter.user_link_formatter,
    }
    column_formatters_detail = column_formatters
    column_searchable_list = [
        Product.id,
        Product.name,
        Product.description,
        Product.moderation_comment,
    ]
    can_delete = False
    name = 'Product'
    name_plural = 'Products'
    icon = 'fa-solid fa-box'
    form_columns = [
        Product.status,
        Product.moderator_id,
        Product.moderation_comment,
    ]


class OrderAdmin(ModelView, model=Order):
    """
    Admin panel view for viewing customer orders.

    Provides read-only access to order records with formatted status
    badges and user links. Creation, editing, and deletion are disabled.
    """

    column_list = [
        Order.id,
        Order.user_id,
        Order.status,
        Order.total_amount,
        Order.created_at,
    ]
    column_searchable_list = [Order.id, Order.user_id]
    can_delete = False
    name = 'Order'
    name_plural = 'Orders'
    icon = 'fa-solid fa-receipt'
    column_formatters = {
        'status': AdminPanelFormatter.status_formatter,
        'user_id': AdminPanelFormatter.user_link_formatter,
    }
    column_formatters_detail = column_formatters
    column_default_sort = [('created_at', True)]


class ReservationAdmin(ModelView, model=Reservation):
    """
    Admin panel view for viewing product reservations.

    Displays reservation details including product, user, quantity, and
    expiration time. All mutations (create, edit, delete) are disabled.
    """

    column_list = [
        Reservation.id,
        Reservation.product_id,
        Reservation.user_id,
        Reservation.qty_reserved,
        Reservation.status,
        Reservation.created_at,
        Reservation.expires_at,
    ]
    column_searchable_list = [Reservation.id, Reservation.user_id]
    can_delete = False
    name = 'Reservation'
    name_plural = 'Reservations'
    icon = 'fa-solid fa-cart-arrow-down'
    column_formatters = {
        'user_id': AdminPanelFormatter.user_link_formatter,
        'product_id': AdminPanelFormatter.product_link_formatter,
        'status': AdminPanelFormatter.status_formatter,
        'order_id': AdminPanelFormatter.order_link_formatter,
    }
    column_formatters_detail = column_formatters
    column_default_sort = [('created_at', True)]
    column_labels = {'qty_reserved': 'Quantity reserved'}


class AuditLogAdmin(AdminAccessMixin, model=AuditLog):
    """
    Admin panel view for viewing audit log entries.

    Provides read-only access to the audit trail, showing all recorded
    actions, target objects, and actors. Restricted to ``ADMIN`` role.
    """

    column_list = [
        AuditLog.id,
        AuditLog.target_type,
        AuditLog.target_id,
        AuditLog.actor_id,
        AuditLog.action,
    ]
    column_searchable_list = [AuditLog.target_type, AuditLog.target_id, AuditLog.action]
    can_create = False
    can_edit = False
    can_delete = False
    name = 'Audit Log'
    name_plural = 'Audit Logs'
    icon = 'fa-solid fa-clipboard-list'
    column_default_sort = [('created_at', True)]
    column_formatters = {
        'actor_id': AdminPanelFormatter.user_link_formatter,
        'target_id': AdminPanelFormatter.order_link_formatter,
    }
    column_formatters_detail = column_formatters


class APIKeyB2BPartnerAdmin(AdminAccessMixin, model=APIKeyB2BPartner):
    """
    Admin panel view for managing B2B partner API keys.

    Displays API key records with user associations, key names, and
    prefixes. Restricted to ``ADMIN`` role. Deletion is disabled.
    """

    column_list = [
        APIKeyB2BPartner.id,
        APIKeyB2BPartner.user_id,
        APIKeyB2BPartner.name,
        APIKeyB2BPartner.key_prefix,
        APIKeyB2BPartner.is_active,
    ]
    column_searchable_list = [APIKeyB2BPartner.name, APIKeyB2BPartner.key_prefix]
    can_delete = False
    name = 'API Key'
    name_plural = 'API Keys'
    icon = 'fa-solid fa-key'
    column_default_sort = [('created_at', True)]
    column_formatters = {
        'user_id': AdminPanelFormatter.user_link_formatter,
    }
    column_formatters_detail = column_formatters


def register_admin_views(admin: Any) -> None:
    """
    Register all admin model views with the SQLAdmin instance.

    Adds each admin view class (users, products, orders, reservations,
    audit logs, API keys, and verification requests) to the provided
    admin object.

    Args:
        admin: The SQLAdmin ``Admin`` instance to register views with.
    """
    admin.add_view(UserAdmin)
    admin.add_view(ProductAdmin)
    admin.add_view(OrderAdmin)
    admin.add_view(ReservationAdmin)
    admin.add_view(AuditLogAdmin)
    admin.add_view(APIKeyB2BPartnerAdmin)
    admin.add_view(VerificationRequestAdmin)
