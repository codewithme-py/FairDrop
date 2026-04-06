from typing import Annotated

from fastapi import Depends, Request
from jose import JWTError, jwt
from sqlalchemy import select

from app.core.auth_schemes import header_scheme, oauth2_scheme, oauth2_scheme_optional
from app.core.config import settings
from app.core.database import SessionDep
from app.core.exceptions import CredentialsError, PermissionDeniedError
from app.services.user.models import User
from app.services.user.service import UserService


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: SessionDep,
) -> User:
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        email: str | None = payload.get('sub')
        if email is None:
            raise CredentialsError()
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            raise CredentialsError()
        return user
    except JWTError:
        raise CredentialsError()


async def get_current_user_flexible(
    request: Request,
    session: SessionDep,
    token: str | None = Depends(oauth2_scheme_optional),
) -> User:
    if token:
        try:
            return await get_current_user(token, session)
        except CredentialsError:
            pass
    user_id = request.session.get('token')
    if user_id:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            return user

    raise CredentialsError()


async def get_api_key_user(
    api_key: Annotated[str | None, Depends(header_scheme)],
    session: SessionDep,
) -> User:
    if not api_key:
        raise PermissionDeniedError('Missing API Key')
    api_key_record = await UserService.authenticate_api_key_b2b_partner(
        session, api_key
    )
    if not api_key_record:
        raise PermissionDeniedError('Invalid API Key')
    return api_key_record.user
