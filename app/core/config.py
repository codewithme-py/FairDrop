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
    redis_host: str = Field(alias='REDIS_HOST')
    redis_port: int = Field(alias='REDIS_PORT')
    s3_host: str = Field(alias='S3_HOST')
    s3_port: int = Field(alias='S3_PORT')
    minio_root_user: str = Field(alias='MINIO_ROOT_USER')
    minio_root_password: str = Field(alias='MINIO_ROOT_PASSWORD')
    debug_mode: bool = Field(default=False, alias='DEBUG_MODE')

    @computed_field
    def database_url(self) -> str:
        return f'postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}'


settings = Settings()
