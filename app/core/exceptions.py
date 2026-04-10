class AppError(Exception):
    """
    Base class for all application-level errors.

    Attributes:
        message: A human-readable error description.
        headers: Optional HTTP headers to include in the error response.
    """

    def __init__(self, message: str = '', headers: dict | None = None):
        """
        Initialize the AppError.

        Args:
            message: A human-readable error description.
            headers: Optional HTTP headers to include in the error response.
        """
        self.message = message
        self.headers = headers
        super().__init__(message)


class UserAlreadyExists(AppError):
    """
    Raised when attempting to register a user with an email that is already taken.
    """


class SellerLimitExceededError(AppError):
    """
    Raised when a seller exceeds their product listing limit.
    """

    def __init__(self, message: str = 'Seller product listing limit exceeded'):
        """
        Initialize the SellerLimitExceededError.

        Args:
            message: A human-readable error description.
        """
        super().__init__(message=message)


class CredentialsError(AppError):
    """
    Raised when authentication credentials are invalid or missing.
    """

    def __init__(self, message: str = 'Could not validate credentials'):
        """
        Initialize the CredentialsError.

        Args:
            message: A human-readable error description.
        """
        super().__init__(message=message, headers={'WWW-Authenticate': 'Bearer'})


class NotFoundError(AppError):
    """
    Raised when a requested resource cannot be found.
    """

    def __init__(self, message: str = 'Resource not found'):
        """
        Initialize the NotFoundError.

        Args:
            message: A human-readable error description.
        """
        super().__init__(message=message)


class ConflictError(AppError):
    """
    Raised when a resource operation conflicts with existing state.
    """

    def __init__(self, message: str = 'Resource conflict'):
        """
        Initialize the ConflictError.

        Args:
            message: A human-readable error description.
        """
        super().__init__(message=message)


class InsufficientInventoryError(AppError):
    """
    Raised when inventory levels are insufficient for an operation.
    """

    def __init__(self, message: str = 'Insufficient inventory'):
        """
        Initialize the InsufficientInventoryError.

        Args:
            message: A human-readable error description.
        """
        super().__init__(message=message)


class PermissionDeniedError(AppError):
    """
    Raised when a user lacks permission to perform an action.
    """

    def __init__(self, message: str = 'Permission denied'):
        """
        Initialize the PermissionDeniedError.

        Args:
            message: A human-readable error description.
        """
        super().__init__(message=message)


class VerificationRequestAlreadyExists(AppError):
    """
    Raised when a verification request already exists for a user.
    """

    def __init__(self, message: str = 'Verification request already exists'):
        """
        Initialize the VerificationRequestAlreadyExists error.

        Args:
            message: A human-readable error description.
        """
        super().__init__(message=message)
