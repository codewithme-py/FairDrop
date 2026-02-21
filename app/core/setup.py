from fastapi import FastAPI

from .exception_handlers import (
    conflict_error_handler,
    credentials_error_handler,
    insufficient_inventory_error_handler,
    not_found_error_handler,
    user_already_exists_handler,
)
from .exceptions import (
    ConflictError,
    CredentialsError,
    InsufficientInventoryError,
    NotFoundError,
    UserAlreadyExists,
)


def setup_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(UserAlreadyExists, user_already_exists_handler)  # type: ignore[arg-type]
    app.add_exception_handler(CredentialsError, credentials_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ConflictError, conflict_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(NotFoundError, not_found_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(
        InsufficientInventoryError,
        insufficient_inventory_error_handler,  # type: ignore[arg-type]
    )
