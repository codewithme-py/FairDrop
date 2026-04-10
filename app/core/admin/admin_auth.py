from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import select
from starlette.requests import Request

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.exceptions import PermissionDeniedError
from app.core.security import check_permission
from app.services.user.models import User, UserRole
from app.services.user.service import UserService


class AdminAuth(AuthenticationBackend):
    """
    Authentication backend for the SQLAdmin panel using session-based login.

    Handles login, logout, and authentication for admin panel users. Only
    users with the ADMIN or MODERATOR role are granted access.
    """

    async def login(self, request: Request) -> bool:
        """
        Authenticate an admin user via email and password from a form.

        Extracts the username (email) and password fields from the
        submitted form, validates the credentials, and checks that the user
        has an admin or moderator role. On success, stores the user ID in
        the session.

        Args:
            request: The incoming Starlette request containing form data with
                username and password fields.

        Returns:
            True if authentication succeeds and the user has the
            required role; False otherwise.
        """
        user_data = await request.form()
        email = user_data.get('username')
        password = user_data.get('password')

        if not isinstance(email, str) or not isinstance(password, str):
            return False

        async with async_session_factory() as session:
            user = await UserService.authenticate_user(session, email, password)
            if user is None:
                return False

            try:
                await check_permission(user, [UserRole.ADMIN, UserRole.MODERATOR])
                request.session['token'] = str(user.id)
                return True
            except PermissionDeniedError:
                return False

    async def logout(self, request: Request) -> bool:
        """
        Log out the current admin user by clearing the session.

        Args:
            request: The incoming Starlette request with an active session.

        Returns:
            Always returns True after clearing the session.
        """
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """
        Verify that the current session holds a valid admin or moderator user.

        Looks up the user ID stored in the session under the token key
        and checks that the corresponding user exists and has either the
        ADMIN or MODERATOR role. The authenticated user is attached
        to request.state for downstream use.

        Args:
            request: The incoming Starlette request with a session.

        Returns:
            True if a valid admin/moderator user is authenticated;
            False if the session is empty or the user is invalid.
        """
        token = request.session.get('token')
        if not token:
            return False

        async with async_session_factory() as session:
            result = await session.execute(select(User).where(User.id == token))
            user = result.scalar_one_or_none()
            if not user or user.role not in (UserRole.ADMIN, UserRole.MODERATOR):
                return False
            request.state.user = user
        return True


authentication_backend = AdminAuth(secret_key=settings.secret_key)
