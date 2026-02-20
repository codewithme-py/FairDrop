from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import CredentialsError
from app.core.security import create_access_token
from app.services.user.models import User
from app.services.user.schemas import RefreshTokenRequest, Token, UserCreate, UserRead
from app.services.user.service import UserService
from app.shared.deps import get_current_user

router_v1 = APIRouter()


@router_v1.post('/users', status_code=status.HTTP_201_CREATED)
async def create_user(
    user_create: UserCreate, session: Annotated[AsyncSession, Depends(get_session)]
) -> UserRead:
    user = await UserService.create_user(session, user_create)
    return UserRead.model_validate(user)


@router_v1.post('/auth/token')
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Token:
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
    session: Annotated[AsyncSession, Depends(get_session)],
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
