from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
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
    await limit_signup_attempts(request)
    user = await UserService.create_user(session, user_create)
    return UserRead.model_validate(user)


@router_v1.post('/auth/token')
async def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
) -> Token:
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
    verification_request = await UserService.create_verification_request(
        session=session,
        user_id=current_user.id,
        target_role=schema.target_role,
        docs_url=schema.docs_url,
    )
    return VerificationRequestRead.model_validate(verification_request)
