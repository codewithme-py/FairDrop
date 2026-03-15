from fastapi import Request, status
from fastapi.responses import JSONResponse

from .exceptions import (
    ConflictError,
    CredentialsError,
    InsufficientInventoryError,
    NotFoundError,
    PermissionDeniedError,
    UserAlreadyExists,
)

EXISTING_USER_MESSAGE = 'User already exists'
INVALID_CREDENTIALS_MESSAGE = 'Invalid credentials'
NOT_FOUND_MESSAGE = 'Resource not found'
INSUFFICIENT_INVENTORY_MESSAGE = 'Insufficient inventory'
CONFLICT_MESSAGE = 'Resource conflict'


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


async def not_found_error_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={'detail': str(exc) or NOT_FOUND_MESSAGE},
    )


async def insufficient_inventory_error_handler(
    request: Request, exc: InsufficientInventoryError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={'detail': str(exc) or INSUFFICIENT_INVENTORY_MESSAGE},
    )


async def conflict_error_handler(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={'detail': str(exc) or CONFLICT_MESSAGE},
    )


async def permission_denied_handler(
    request: Request, exc: PermissionDeniedError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={'detail': str(exc) or 'Permission denied'},
    )
