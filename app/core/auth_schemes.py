from fastapi.security import APIKeyHeader, OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/token')
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl='/api/v1/auth/token', auto_error=False
)
header_scheme = APIKeyHeader(name='X-API-Key', auto_error=False)
