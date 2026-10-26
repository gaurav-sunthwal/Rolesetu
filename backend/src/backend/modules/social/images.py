"""Images for social posts: checked, turned into JPEG, kept in R2, and served
from a public address on this API.

Facebook and Instagram download a post's image from a link, so it has to be
public. The bucket stays private; only these post images are served, by an
id nobody can guess. Every image becomes a JPEG because that is the one
format Instagram accepts.
"""

import asyncio
import re
import uuid

import pymupdf

from backend.core import storage
from backend.core.config import get_settings
from backend.core.exceptions import NotFoundError, ValidationFailedError

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 40_000_000
_PREFIX = "social/"
NAME = re.compile(r"^[0-9a-f]{32}\.jpg$")


def to_jpeg(data: bytes) -> bytes:
    """The image as a JPEG on white, or a refusal a person can act on."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationFailedError("The image is larger than 8 MB.")
    try:
        pixmap = pymupdf.Pixmap(data)
    except Exception as exc:
        raise ValidationFailedError(
            "That file is not an image we can read. Use a JPEG or PNG."
        ) from exc
    if pixmap.width * pixmap.height > MAX_PIXELS:
        raise ValidationFailedError("The image is too large. Keep it under 40 megapixels.")
    if pixmap.alpha:
        pixmap = pymupdf.Pixmap(pixmap, 0)
    if pixmap.colorspace is None or pixmap.colorspace.n != 3:
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pixmap)
    jpeg: bytes = pixmap.tobytes("jpeg", jpg_quality=88)
    return jpeg


def public_url(name: str) -> str:
    base = get_settings().public_api_url.rstrip("/")
    return f"{base}/api/v1/public/social-images/{name}"


async def save(data: bytes) -> str:
    """Stores an uploaded image and returns the public link to it."""
    jpeg = await asyncio.to_thread(to_jpeg, data)
    name = f"{uuid.uuid4().hex}.jpg"
    await storage.put_file(_PREFIX + name, jpeg, content_type="image/jpeg")
    return public_url(name)


async def read(name: str) -> bytes:
    if not NAME.match(name):
        raise NotFoundError("Image not found.")
    return await storage.get_file(_PREFIX + name)
