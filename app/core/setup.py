from fastapi import FastAPI

from .exception_handlers import (
    conflict_error_handler,
    credentials_error_handler,
    insufficient_inventory_error_handler,
    not_found_error_handler,
    permission_denied_handler,
    seller_limit_exceeded_handler,
    user_already_exists_handler,
    verification_request_already_exists_handler,
)
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


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Register custom exception handlers on the FastAPI application.

    Maps each application-specific exception class to its corresponding
    HTTP response handler, ensuring consistent error responses.

    Args:
        app: The FastAPI application instance.
    """
    app.add_exception_handler(UserAlreadyExists, user_already_exists_handler)  # type: ignore[arg-type]
    app.add_exception_handler(CredentialsError, credentials_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ConflictError, conflict_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(NotFoundError, not_found_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(
        InsufficientInventoryError,
        insufficient_inventory_error_handler,  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        PermissionDeniedError,
        permission_denied_handler,  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        VerificationRequestAlreadyExists,
        verification_request_already_exists_handler,  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        SellerLimitExceededError,
        seller_limit_exceeded_handler,  # type: ignore[arg-type]
    )
