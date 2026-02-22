from uuid import UUID

from pydantic import BaseModel, Field


class ImageUploadRequest(BaseModel):
    filename: str
    content_type: str


class ImageUploadResponse(BaseModel):
    image_id: UUID
    url: str
    fields: dict[str, str]


class S3Object(BaseModel):
    key: str


class S3Entity(BaseModel):
    object: S3Object


class S3Record(BaseModel):
    event_name: str = Field(alias='eventName')
    s3: S3Entity


class MinioWebhookEvent(BaseModel):
    records: list[S3Record] = Field(alias='Records')
