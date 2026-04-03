from fastapi import Request

from app.core.config import settings
from app.shared.rate_limit import check_rate_limit


async def limit_login_attempts(request: Request, email: str) -> None:
    await check_rate_limit(
        rate_limit_script=request.app.state.rate_limit_script,
        keys=[f'rate_limit:login:{email}'],
        limits=[settings.login_rate_limit_attempts],
        ttl=settings.login_rate_limit_ttl,
    )


async def limit_signup_attempts(request: Request) -> None:
    remote_ip = request.client.host if request.client else 'unknown'
    await check_rate_limit(
        rate_limit_script=request.app.state.rate_limit_script,
        keys=[f'rate_limit:signup:{remote_ip}'],
        limits=[settings.signup_rate_limit_attempts],
        ttl=settings.signup_rate_limit_ttl,
    )
