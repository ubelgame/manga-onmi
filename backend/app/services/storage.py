import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from app.core.config import get_settings
import io
import uuid

settings = get_settings()

def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )

def ensure_bucket_exists():
    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        s3.create_bucket(Bucket=settings.s3_bucket)

def upload_image_bytes(image_bytes: bytes, prefix: str = "pages") -> str:
    """Upload raw bytes and return the S3 key."""
    s3 = get_s3_client()
    key = f"{prefix}/{uuid.uuid4()}.jpg"
    s3.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=image_bytes,
        ContentType="image/jpeg",
    )
    return key

def download_image_bytes(key: str) -> bytes:
    """Download S3 object and return raw bytes."""
    s3 = get_s3_client()
    response = s3.get_object(Bucket=settings.s3_bucket, Key=key)
    return response["Body"].read()

def get_presigned_url(key: str, expires: int = 3600) -> str:
    """Generate a time-limited public URL for the frontend to display."""
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires,
    )

def download_to_file(key: str, local_path: str):
    s3 = get_s3_client()
    s3.download_file(settings.s3_bucket, key, local_path)
