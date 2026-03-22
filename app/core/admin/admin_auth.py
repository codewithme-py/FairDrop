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
    async def login(self, request: Request) -> bool:
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
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
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
