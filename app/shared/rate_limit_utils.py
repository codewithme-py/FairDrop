from fastapi import Request

from app.core.config import settings
from app.shared.rate_limit import check_rate_limit


async def limit_login_attempts(request: Request, email: str) -> None:
    """
    Enforce a rate limit on login attempts for a specific email address.

    Checks whether the number of login attempts for the given email has
    exceeded the configured threshold within the current time window.

    Args:
        request: The incoming HTTP request, used to access the rate limit
            Lua script registered on the Redis connection.
        email: The email address of the user attempting to log in.

    Raises:
        HTTPException: 429 error if the rate limit for this email has been
            exceeded.
    """
    await check_rate_limit(
        rate_limit_script=request.app.state.rate_limit_script,
        keys=[f'rate_limit:login:{email}'],
        limits=[settings.login_rate_limit_attempts],
        ttl=settings.login_rate_limit_ttl,
    )


async def limit_signup_attempts(request: Request) -> None:
    """
    Enforce a rate limit on signup attempts based on the client's IP address.

    Checks whether the number of signup requests from the client's remote
    IP has exceeded the configured threshold within the current time window.

    Args:
        request: The incoming HTTP request, used to determine the client's
            IP address and access the rate limit Lua script.

    Raises:
        HTTPException: 429 error if the rate limit for this IP address has
            been exceeded.
    """
    remote_ip = request.client.host if request.client else 'unknown'
    await check_rate_limit(
        rate_limit_script=request.app.state.rate_limit_script,
        keys=[f'rate_limit:signup:{remote_ip}'],
        limits=[settings.signup_rate_limit_attempts],
        ttl=settings.signup_rate_limit_ttl,
    )
