class AppError(Exception):
    """Base class for all application errors."""

    def __init__(self, message: str = '', headers: dict | None = None):
        self.message = message
        self.headers = headers
        super().__init__(message)


class UserAlreadyExists(AppError):
    """User with such email already exists."""


class SellerLimitExceededError(AppError):
    """Seller product listing limit exceeded."""

    def __init__(self, message: str = 'Seller product listing limit exceeded'):
        super().__init__(message=message)


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


class PermissionDeniedError(AppError):
    """Permission denied."""

    def __init__(self, message: str = 'Permission denied'):
        super().__init__(message=message)


class VerificationRequestAlreadyExists(AppError):
    """Verification request already exists."""

    def __init__(self, message: str = 'Verification request already exists'):
        super().__init__(message=message)
