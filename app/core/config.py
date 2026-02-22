from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_port: int = Field(alias='APP_PORT')
    db_user: str = Field(alias='POSTGRES_USER')
    db_password: str = Field(alias='POSTGRES_PASSWORD')
    db_host: str = Field(alias='DB_HOST')
    db_port: int = Field(alias='DB_PORT')
    db_name: str = Field(alias='POSTGRES_DB')
    redis_prefix: str = Field(alias='REDIS_PREFIX')
    redis_host: str = Field(alias='REDIS_HOST')
    redis_port: int = Field(alias='REDIS_PORT')
    redis_url: str = Field(alias='REDIS_URL')
    s3_host: str = Field(alias='S3_HOST')
    s3_port: int = Field(alias='S3_PORT')
    minio_root_user: str = Field(alias='MINIO_ROOT_USER')
    minio_root_password: str = Field(alias='MINIO_ROOT_PASSWORD')
    minio_bucket_name: str = Field(alias='MINIO_BUCKET_NAME')
    minio_url: str = Field(alias='MINIO_URL')
    pool_size: int = Field(alias='POOL_SIZE')
    max_overflow: int = Field(alias='MAX_OVERFLOW')
    jwt_algorithm: str = Field(default='HS256', alias='JWT_ALGORITHM')
    access_token_expire_minutes: int = Field(alias='ACCESS_TOKEN_EXPIRE_MINUTES')
    refresh_token_expire_days: int = Field(alias='REFRESH_TOKEN_EXPIRE_DAYS')
    rate_limit_user_rps: int = Field(alias='RATE_LIMIT_USER_RPS')
    rate_limit_global_rps: int = Field(alias='RATE_LIMIT_GLOBAL_RPS')
    rate_limit_ttl_seconds: int = Field(alias='RATE_LIMIT_TTL_SECONDS')
    idempotent_key_lifetime_sec: int = Field(alias='IDEMPOTENT_KEY_LIFETIME_SEC')
    reserve_timeout_minutes: int = Field(alias='RESERVE_TIMEOUT_MINUTES')
    presigned_url_expire_seconds: int = Field(alias='PRESIGNED_URL_EXPIRE_SECONDS')
    min_file_size_bytes: int = Field(alias='MIN_FILE_SIZE_BYTES')
    max_file_size_bytes: int = Field(alias='MAX_FILE_SIZE_BYTES')
    secret_key: str = Field(alias='SECRET_KEY')
    debug_mode: bool = Field(default=False, alias='DEBUG_MODE')

    @computed_field
    def database_url(self) -> str:
        return f'postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}'


settings = Settings()
