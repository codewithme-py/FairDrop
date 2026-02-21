class AppError(Exception):
    """Base class for all application errors."""

    def __init__(self, message: str = '', headers: dict | None = None):
        self.message = message
        self.headers = headers
        super().__init__(message)


class UserAlreadyExists(AppError):
    """User with such email already exists."""


class CredentialsError(AppError):
    """Invalid credentials."""

    def __init__(self, message: str = 'Could not validate credentials'):
        super().__init__(message=message, headers={'WWW-Authenticate': 'Bearer'})


class NotFoundError(AppError):
    """Resource not found."""

    def __init__(self, message: str = 'Resource not found'):
        super().__init__(message=message)


class ConflictError(AppError):
    """Resource conflict."""

    def __init__(self, message: str = 'Resource conflict'):
        super().__init__(message=message)


class InsufficientInventoryError(AppError):
    """Insufficient inventory."""

    def __init__(self, message: str = 'Insufficient inventory'):
        super().__init__(message=message)
