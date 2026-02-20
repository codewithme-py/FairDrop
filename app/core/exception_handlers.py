from fastapi import Request, status
from fastapi.responses import JSONResponse

from .exceptions import CredentialsError, UserAlreadyExists

EXISTING_USER_MESSAGE = 'User already exists'
INVALID_CREDENTIALS_MESSAGE = 'Invalid credentials'


async def user_already_exists_handler(
    request: Request, exc: UserAlreadyExists
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={'detail': str(exc) or EXISTING_USER_MESSAGE},
    )


async def credentials_error_handler(
    request: Request, exc: CredentialsError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={'detail': str(exc) or INVALID_CREDENTIALS_MESSAGE},
        headers=getattr(exc, 'headers', None),
    )
