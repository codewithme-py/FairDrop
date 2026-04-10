from fastapi import Request, status
from fastapi.responses import JSONResponse

from .exceptions import (
    ConflictError,
    CredentialsError,
    InsufficientInventoryError,
    NotFoundError,
    PermissionDeniedError,
    SellerLimitExceededError,
    UserAlreadyExists,
    VerificationRequestAlreadyExists,
)

EXISTING_USER_MESSAGE = 'User already exists'
INVALID_CREDENTIALS_MESSAGE = 'Invalid credentials'
NOT_FOUND_MESSAGE = 'Resource not found'
INSUFFICIENT_INVENTORY_MESSAGE = 'Insufficient inventory'
CONFLICT_MESSAGE = 'Resource conflict'


async def user_already_exists_handler(
    request: Request, exc: UserAlreadyExists
) -> JSONResponse:
    """
    Handle UserAlreadyExists exceptions.

    Args:
        request: The HTTP request that triggered the exception.
        exc: The caught exception instance.

    Returns:
        A 400 JSON response with the error detail.
    """
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={'detail': str(exc) or EXISTING_USER_MESSAGE},
    )


async def credentials_error_handler(
    request: Request, exc: CredentialsError
) -> JSONResponse:
    """
    Handle CredentialsError exceptions.

    Args:
        request: The HTTP request that triggered the exception.
        exc: The caught exception instance.

    Returns:
        A 401 JSON response with authentication challenge headers.
    """
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={'detail': str(exc) or INVALID_CREDENTIALS_MESSAGE},
        headers=getattr(exc, 'headers', None),
    )


async def not_found_error_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    """
    Handle NotFoundError exceptions.

    Args:
        request: The HTTP request that triggered the exception.
        exc: The caught exception instance.

    Returns:
        A 404 JSON response with the error detail.
    """
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={'detail': str(exc) or NOT_FOUND_MESSAGE},
    )


async def insufficient_inventory_error_handler(
    request: Request, exc: InsufficientInventoryError
) -> JSONResponse:
    """
    Handle InsufficientInventoryError exceptions.

    Args:
        request: The HTTP request that triggered the exception.
        exc: The caught exception instance.

    Returns:
        A 400 JSON response with the error detail.
    """
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={'detail': str(exc) or INSUFFICIENT_INVENTORY_MESSAGE},
    )


async def conflict_error_handler(request: Request, exc: ConflictError) -> JSONResponse:
    """
    Handle ConflictError exceptions.

    Args:
        request: The HTTP request that triggered the exception.
        exc: The caught exception instance.

    Returns:
        A 409 JSON response with the error detail.
    """
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={'detail': str(exc) or CONFLICT_MESSAGE},
    )


async def permission_denied_handler(
    request: Request, exc: PermissionDeniedError
) -> JSONResponse:
    """
    Handle PermissionDeniedError exceptions.

    Args:
        request: The HTTP request that triggered the exception.
        exc: The caught exception instance.

    Returns:
        A 403 JSON response with the error detail.
    """
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={'detail': str(exc) or 'Permission denied'},
    )


async def verification_request_already_exists_handler(
    request: Request, exc: VerificationRequestAlreadyExists
) -> JSONResponse:
    """
    Handle VerificationRequestAlreadyExists exceptions.

    Args:
        request: The HTTP request that triggered the exception.
        exc: The caught exception instance.

    Returns:
        A 400 JSON response with the error detail.
    """
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={'detail': str(exc) or 'Verification request already exists'},
    )


async def seller_limit_exceeded_handler(
    request: Request, exc: SellerLimitExceededError
) -> JSONResponse:
    """
    Handle SellerLimitExceededError exceptions.

    Args:
        request: The HTTP request that triggered the exception.
        exc: The caught exception instance.

    Returns:
        A 400 JSON response with the error detail.
    """
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={'detail': str(exc) or 'Seller limit exceeded'},
    )
