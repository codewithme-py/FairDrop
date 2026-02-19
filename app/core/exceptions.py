class AppError(Exception):
    """Базовый класс для всех ошибок приложения."""

    def __init__(self, message: str = '', headers: dict | None = None):
        self.message = message
        self.headers = headers
        super().__init__(message)


class UserAlreadyExists(AppError):
    """Пользователь c таким email уже существует."""


class CredentialsError(AppError):
    """Неверные учетные данные."""

    def __init__(self, message: str = 'Could not validate credentials'):
        super().__init__(message=message, headers={'WWW-Authenticate': 'Bearer'})
