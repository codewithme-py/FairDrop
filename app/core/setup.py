from fastapi import FastAPI

from .exception_handlers import credentials_error_handler, user_already_exists_handler
from .exceptions import CredentialsError, UserAlreadyExists


def setup_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(UserAlreadyExists, user_already_exists_handler)  # type: ignore[arg-type]
    app.add_exception_handler(CredentialsError, credentials_error_handler)  # type: ignore[arg-type]
