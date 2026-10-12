"""Private file storage on Cloudflare R2 (S3-compatible).

Nothing here is ever public: files are only reachable through short-lived
signed URLs. boto3 is blocking, so every call runs in a worker thread.
"""

import asyncio
from functools import lru_cache
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from backend.core.config import get_settings
from backend.core.exceptions import AppError

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


class StorageUnavailableError(AppError):
    status_code = 503
    detail = "File storage is unavailable right now. Please try again in a moment."


@lru_cache
def _client() -> "S3Client":
    settings = get_settings()
    if not (settings.r2_account_id and settings.r2_access_key_id and settings.r2_secret_access_key):
        raise StorageUnavailableError("File storage is not configured.")
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
        config=Config(
            signature_version="s3v4",
            connect_timeout=10,
            read_timeout=30,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def _bucket() -> str:
    bucket = get_settings().r2_bucket
    if not bucket:
        raise StorageUnavailableError("File storage is not configured.")
    return bucket


async def put_file(key: str, data: bytes, *, content_type: str) -> None:
    try:
        await asyncio.to_thread(
            _client().put_object, Bucket=_bucket(), Key=key, Body=data, ContentType=content_type
        )
    except (BotoCoreError, ClientError) as exc:
        raise StorageUnavailableError() from exc


async def get_file(key: str) -> bytes:
    def read() -> bytes:
        return _client().get_object(Bucket=_bucket(), Key=key)["Body"].read()

    try:
        return await asyncio.to_thread(read)
    except (BotoCoreError, ClientError) as exc:
        raise StorageUnavailableError() from exc


async def delete_file(key: str) -> None:
    try:
        await asyncio.to_thread(_client().delete_object, Bucket=_bucket(), Key=key)
    except (BotoCoreError, ClientError) as exc:
        raise StorageUnavailableError() from exc


async def signed_download_url(key: str, *, filename: str, expires_in: int = 300) -> str:
    """A link that works for a few minutes, then stops."""
    safe_name = filename.replace('"', "").replace("\\", "")
    try:
        return await asyncio.to_thread(
            _client().generate_presigned_url,
            "get_object",
            Params={
                "Bucket": _bucket(),
                "Key": key,
                "ResponseContentDisposition": f'inline; filename="{safe_name}"',
                "ResponseContentType": "application/pdf",
            },
            ExpiresIn=expires_in,
        )
    except (BotoCoreError, ClientError) as exc:
        raise StorageUnavailableError() from exc
