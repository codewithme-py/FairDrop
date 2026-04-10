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
    """
    Retrieve the currently authenticated user from a JWT access token.

    Decodes the provided OAuth2 bearer token, validates it against the
    application secret key, and loads the corresponding User record
    from the database.

    Args:
        token: The JWT access token extracted from the Authorization header.
        session: The async SQLAlchemy database session.

    Returns:
        The User instance corresponding to the token's sub claim.

    Raises:
        CredentialsError: If the token is invalid, expired, or the associated
            user does not exist in the database.
    """
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
    """
    Retrieve the authenticated user using multiple authentication strategies.

    Attempts to authenticate the user first via an optional OAuth2 bearer
    token. If that fails, falls back to a session-based token stored in
    request.session. This flexible approach supports both API clients
    (using JWT tokens) and browser-based sessions.

    Args:
        request: The incoming HTTP request, used to access session data.
        session: The async SQLAlchemy database session.
        token: An optional JWT access token. If None or invalid,
            session-based authentication is attempted.

    Returns:
        The authenticated User instance.

    Raises:
        CredentialsError: If neither the JWT token nor the session token
            yields a valid authenticated user.
    """
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
    """
    Authenticate and retrieve the user associated with a B2B API key.

    Validates that an API key is present in the request headers, then
    looks up the corresponding APIKeyB2BPartner record to find the
    associated User.

    Args:
        api_key: The API key extracted from the X-API-Key header.
        session: The async SQLAlchemy database session.

    Returns:
        The User instance associated with the provided API key.

    Raises:
        PermissionDeniedError: If the API key header is missing or the
            key does not correspond to a valid B2B partner record.
    """
    if not api_key:
        raise PermissionDeniedError('Missing API Key')
    api_key_record = await UserService.authenticate_api_key_b2b_partner(
        session, api_key
    )
    if not api_key_record:
        raise PermissionDeniedError('Invalid API Key')
    return api_key_record.user
