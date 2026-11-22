"""Reels for social posts: checked, kept privately in R2, and reached through
short-lived signed links.

Unlike post images, videos are never served by this API: they are large, and
Render's free plan has little memory. The admin panel uploads a reel straight
to R2 with a signed link (`start_upload`, then `confirm`), falling back to
sending it through the API (`save`). Instagram and Facebook download a reel
from a signed R2 link that works for two hours; YouTube is sent the bytes.
"""

import re
import uuid

from fastapi import UploadFile

from backend.core import storage
from backend.core.config import get_settings
from backend.core.exceptions import ValidationFailedError

_PREFIX = "social/videos/"
KEY = re.compile(r"^social/videos/[0-9a-f]{32}\.mp4$")
# Long enough to watch in the admin panel, and for a platform to fetch the file.
PREVIEW_SECONDS = 3 * 3600
PLATFORM_SECONDS = 2 * 3600
UPLOAD_SECONDS = 30 * 60


def max_bytes() -> int:
    return get_settings().social_video_max_mb * 1024 * 1024


def _check_size(size: int) -> None:
    if size > max_bytes():
        raise ValidationFailedError(
            f"The video is larger than {get_settings().social_video_max_mb} MB."
        )


def _new_key() -> str:
    return f"{_PREFIX}{uuid.uuid4().hex}.mp4"


async def start_upload(size: int) -> tuple[str, str]:
    """A new key and a link the browser uploads the reel to directly."""
    _check_size(size)
    key = _new_key()
    url = await storage.signed_upload_url(key, content_type="video/mp4", expires_in=UPLOAD_SECONDS)
    return key, url


async def confirm(key: str) -> int:
    """Checks a reel the browser uploaded: it is there, small enough and an MP4.
    Returns its size. A file that fails is removed."""
    size = await storage.file_size(key)
    if size is None:
        raise ValidationFailedError("The upload did not arrive. Try uploading again.")
    try:
        _check_size(size)
        if not is_mp4(await storage.read_start(key, 12)):
            raise ValidationFailedError("Upload an MP4 video (.mp4).")
    except ValidationFailedError:
        await storage.delete_file(key)
        raise
    return size


def is_mp4(head: bytes) -> bool:
    """MP4 files say "ftyp" in bytes 4 to 8."""
    return len(head) >= 8 and head[4:8] == b"ftyp"


async def save(upload: UploadFile) -> tuple[str, int]:
    """Stores an uploaded reel. Returns its key and size in bytes."""
    upload.file.seek(0, 2)
    size = upload.file.tell()
    upload.file.seek(0)
    _check_size(size)
    if not is_mp4(upload.file.read(12)):
        raise ValidationFailedError("Upload an MP4 video (.mp4).")
    upload.file.seek(0)
    key = _new_key()
    await storage.put_stream(key, upload.file, content_type="video/mp4")
    return key, size


async def link(key: str, seconds: int = PREVIEW_SECONDS) -> str:
    return await storage.signed_url(key, content_type="video/mp4", expires_in=seconds)


async def read(key: str) -> bytes:
    return await storage.get_file(key)


async def delete(key: str) -> None:
    await storage.delete_file(key)
