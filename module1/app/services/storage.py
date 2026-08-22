"""
S3-compatible file storage service.

Uses boto3 under the hood.
For local development, point S3_ENDPOINT_URL at a MinIO container.
For production, remove S3_ENDPOINT_URL and use real AWS credentials.
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


def _get_client():
    """Return a configured boto3 S3 client."""
    kwargs = {
        "region_name": settings.s3_region,
        "aws_access_key_id": settings.s3_access_key_id,
        "aws_secret_access_key": settings.s3_secret_access_key,
    }
    if settings.s3_endpoint_url:
        # MinIO / custom S3-compatible endpoint
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    return boto3.client("s3", **kwargs)


def ensure_bucket_exists() -> None:
    """Create the bucket if it does not already exist (dev convenience)."""
    client = _get_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket_name)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("404", "NoSuchBucket"):
            logger.info("Bucket %s not found — creating it.", settings.s3_bucket_name)
            if settings.s3_region == "us-east-1":
                client.create_bucket(Bucket=settings.s3_bucket_name)
            else:
                client.create_bucket(
                    Bucket=settings.s3_bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": settings.s3_region},
                )
        else:
            raise


def upload_file(
    file_bytes: bytes,
    s3_key: str,
    content_type: str = "application/octet-stream",
) -> str:
    """
    Upload *file_bytes* to S3 under *s3_key*.

    Returns the s3_key on success.
    Raises on error.
    """
    client = _get_client()
    try:
        client.put_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type,
        )
        logger.info("Uploaded %d bytes → s3://%s/%s", len(file_bytes),
                    settings.s3_bucket_name, s3_key)
        return s3_key
    except ClientError as exc:
        logger.error("S3 upload failed for key %s: %s", s3_key, exc)
        raise


def download_file(s3_key: str) -> bytes:
    """
    Download and return the raw bytes for *s3_key*.

    Raises botocore.exceptions.ClientError if the key does not exist.
    """
    client = _get_client()
    try:
        response = client.get_object(Bucket=settings.s3_bucket_name, Key=s3_key)
        data = response["Body"].read()
        logger.info("Downloaded %d bytes ← s3://%s/%s", len(data),
                    settings.s3_bucket_name, s3_key)
        return data
    except ClientError as exc:
        logger.error("S3 download failed for key %s: %s", s3_key, exc)
        raise


def delete_file(s3_key: str) -> None:
    """Delete *s3_key* from S3 (best-effort, no error if missing)."""
    client = _get_client()
    try:
        client.delete_object(Bucket=settings.s3_bucket_name, Key=s3_key)
        logger.info("Deleted s3://%s/%s", settings.s3_bucket_name, s3_key)
    except ClientError as exc:
        logger.warning("S3 delete failed for key %s: %s", s3_key, exc)


def generate_presigned_url(s3_key: str, expiry_seconds: int = 3600) -> Optional[str]:
    """
    Generate a pre-signed GET URL so the frontend can stream the file directly.

    Returns None if the endpoint doesn't support pre-signed URLs (e.g. plain MinIO without SSL).
    """
    client = _get_client()
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket_name, "Key": s3_key},
            ExpiresIn=expiry_seconds,
        )
        return url
    except ClientError as exc:
        logger.warning("Could not generate presigned URL for %s: %s", s3_key, exc)
        return None
