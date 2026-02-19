from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.exceptions import CredentialsError
from app.core.security import ALGORITHM
from app.services.user.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/token')


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
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
