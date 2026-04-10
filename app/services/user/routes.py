from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.core.database import SessionDep
from app.core.exceptions import CredentialsError
from app.core.security import RoleChecker, create_access_token
from app.services.user.models import APIKeyB2BPartner, User, UserRole
from app.services.user.schemas import (
    APIKeyCreate,
    APIKeyRead,
    APIKeyWithSecret,
    RefreshTokenRequest,
    Token,
    UserCreate,
    UserRead,
    VerificationRequestCreate,
    VerificationRequestRead,
)
from app.services.user.service import UserService
from app.shared.deps import get_current_user
from app.shared.rate_limit_utils import limit_login_attempts, limit_signup_attempts

router_v1 = APIRouter()
B2B_PARTNER_DEP = Depends(RoleChecker([UserRole.USER_B2B, UserRole.SELLER_B2B]))


@router_v1.post('/users', status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    user_create: UserCreate,
    session: SessionDep,
) -> UserRead:
    """
    Register a new user account.

    Args:
        request: FastAPI request object for rate limiting.
        user_create: Registration payload with email and password.
        session: Async database session.

    Returns:
        Created user profile with ID, email, and role.

    Raises:
        UserAlreadyExists: If the email is already registered.
    """
    await limit_signup_attempts(request)
    user = await UserService.create_user(session, user_create)
    return UserRead.model_validate(user)


@router_v1.post('/auth/token')
async def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
) -> Token:
    """
    Authenticate a user and return JWT tokens.

    Args:
        request: FastAPI request object for rate limiting.
        form_data: OAuth2 form with username (email) and password.
        session: Async database session.

    Returns:
        Token response with access token, token type, and refresh token.

    Raises:
        CredentialsError: If the email or password is incorrect.
    """
    await limit_login_attempts(request, form_data.username)
    user = await UserService.authenticate_user(
        session, form_data.username, form_data.password
    )
    if not user:
        raise CredentialsError()
    access_token = create_access_token(data={'sub': str(user.email)})
    refresh_token = await UserService.create_refresh_token(session, user.id)
    return Token(
        access_token=access_token, token_type='bearer', refresh_token=refresh_token
    )


@router_v1.post('/auth/refresh')
async def refresh_token(
    request_data: RefreshTokenRequest,
    session: SessionDep,
) -> Token:
    """
    Refresh an access token using a valid refresh token.

    The old refresh token is consumed and a new one is issued.

    Args:
        request_data: Request containing the refresh token.
        session: Async database session.

    Returns:
        New token response with fresh access and refresh tokens.

    Raises:
        CredentialsError: If the refresh token is invalid or expired.
    """
    user = await UserService.refresh_access_token(session, request_data.refresh_token)
    access_token = create_access_token(data={'sub': str(user.email)})
    refresh_token = await UserService.create_refresh_token(session, user.id)
    return Token(
        access_token=access_token, token_type='bearer', refresh_token=refresh_token
    )


@router_v1.get('/users/me')
async def read_user_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    """
    Retrieve the authenticated user's own profile.

    Args:
        current_user: Authenticated user from the request token.

    Returns:
        User profile with ID, email, and role.
    """
    return UserRead.model_validate(current_user)


@router_v1.post(
    '/users/me/api-keys',
    response_model=APIKeyWithSecret,
    status_code=HTTPStatus.CREATED,
)
async def create_api_key_b2b_partner(
    api_key_create: APIKeyCreate,
    current_user: Annotated[User, B2B_PARTNER_DEP],
    session: SessionDep,
) -> APIKeyWithSecret:
    """
    Create a new B2B API key for the authenticated user.

    The raw key is returned only once at creation time and must be stored
    securely by the client.

    Args:
        api_key_create: Payload containing a human-readable key name.
        current_user: Authenticated B2B partner user.
        session: Async database session.

    Returns:
        API key details including the raw secret key.
    """
    api_key, raw_key = await UserService.create_api_key_b2b_partner(
        session, current_user.id, api_key_create.name
    )
    data = APIKeyRead.model_validate(api_key).model_dump()
    return APIKeyWithSecret(**data, raw_key=raw_key)


@router_v1.get('/users/me/api-keys', response_model=list[APIKeyRead])
async def get_api_keys_b2b_partners(
    current_user: Annotated[User, B2B_PARTNER_DEP],
    session: SessionDep,
) -> list[APIKeyRead]:
    """
    List all B2B API keys owned by the authenticated user.

    Args:
        current_user: Authenticated B2B partner user.
        session: Async database session.

    Returns:
        List of API key metadata (excluding the secret).
    """
    result = await session.execute(
        select(APIKeyB2BPartner).where(APIKeyB2BPartner.user_id == current_user.id)
    )
    api_keys = result.scalars().all()
    return [APIKeyRead.model_validate(api_key) for api_key in api_keys]


@router_v1.delete('/users/me/api-keys/{key_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key_b2b_partner(
    key_id: UUID,
    current_user: Annotated[User, B2B_PARTNER_DEP],
    session: SessionDep,
) -> None:
    """
    Revoke and delete a B2B API key owned by the authenticated user.

    Args:
        key_id: ID of the API key to delete.
        current_user: Authenticated B2B partner user (must own the key).
        session: Async database session.

    Raises:
        NotFoundError: If the API key does not exist or is not owned by the user.
    """
    await UserService.delete_api_key_b2b_partner(session, current_user.id, key_id)


@router_v1.post(
    '/users/me/upgrade-requests',
    status_code=status.HTTP_201_CREATED,
    response_model=VerificationRequestRead,
)
async def create_upgrade_request(
    schema: VerificationRequestCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
) -> VerificationRequestRead:
    """
    Submit a request to upgrade the user's role (e.g., to seller or B2B).

    Only one pending request is allowed per user at a time.

    Args:
        schema: Request payload with target role and optional document URLs.
        current_user: Authenticated user submitting the request.
        session: Async database session.

    Returns:
        The created verification request.

    Raises:
        VerificationRequestAlreadyExists: If a pending request already exists.
        PermissionDeniedError: If the target role is ADMIN or MODERATOR.
    """
    verification_request = await UserService.create_verification_request(
        session=session,
        user_id=current_user.id,
        target_role=schema.target_role,
        docs_url=schema.docs_url,
    )
    return VerificationRequestRead.model_validate(verification_request)


@router_v1.get(
    '/users/me/upgrade-requests', response_model=list[VerificationRequestRead]
)
async def get_upgrade_requests(
    current_user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
) -> list[VerificationRequestRead]:
    """
    List all verification/upgrade requests submitted by the authenticated user.

    Args:
        current_user: Authenticated user.
        session: Async database session.

    Returns:
        List of verification requests ordered by creation date descending.
    """
    requests = await UserService.get_verification_requests(session, current_user.id)
    return [VerificationRequestRead.model_validate(req) for req in requests]


@router_v1.get(
    '/users/me/upgrade-requests/latest', response_model=VerificationRequestRead
)
async def get_latest_upgrade_request(
    current_user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
) -> VerificationRequestRead:
    """
    Retrieve the most recent verification/upgrade request for the authenticated user.

    Args:
        current_user: Authenticated user.
        session: Async database session.

    Returns:
        The latest verification request.

    Raises:
        HTTPException: 404 if the user has no upgrade requests.
    """
    verification_request = await UserService.get_latest_verification_request(
        session, current_user.id
    )
    if not verification_request:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='No upgrade requests found'
        )
    return VerificationRequestRead.model_validate(verification_request)
