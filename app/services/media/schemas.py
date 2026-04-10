from uuid import UUID

from pydantic import BaseModel, Field


class ImageUploadRequest(BaseModel):
    """
    Request body for generating a presigned upload URL.

    Attributes:
        filename: Original name of the image file.
        content_type: MIME type of the image (e.g., 'image/png').
    """

    filename: str
    content_type: str


class ImageUploadResponse(BaseModel):
    """
    Response body containing presigned upload details.

    Attributes:
        image_id: ID of the created ProductImage record.
        url: Presigned S3 upload URL.
        fields: Form fields to include in the S3 POST request.
    """

    image_id: UUID
    url: str
    fields: dict[str, str]


class S3Object(BaseModel):
    """
    Represents an S3 object within a webhook event.

    Attributes:
        key: S3 object key (file path).
    """

    key: str


class S3Entity(BaseModel):
    """
    S3 entity wrapper within a webhook record.

    Attributes:
        object: The S3 object metadata.
    """

    object: S3Object


class S3Record(BaseModel):
    """
    A single record within a MinIO webhook event.

    Attributes:
        event_name: Type of S3 event (e.g., 's3:ObjectCreated:Put').
        s3: S3 entity containing object metadata.
    """

    event_name: str = Field(alias='eventName')
    s3: S3Entity


class MinioWebhookEvent(BaseModel):
    """
    Top-level webhook event payload from MinIO.

    Attributes:
        records: List of S3 event records.
    """

    records: list[S3Record] = Field(alias='Records')
