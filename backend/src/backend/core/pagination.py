"""Cursor pagination helpers.

Lists are ordered by (created_at desc, id desc) and the cursor is the last
row's pair, so a page stays stable while new rows arrive (offset pagination
would shift and repeat or skip rows).
"""

import base64
import binascii
import uuid
from datetime import datetime

from pydantic import BaseModel

from backend.core.exceptions import ValidationFailedError


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None


def encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        created_at, row_id = raw.split("|", 1)
        return datetime.fromisoformat(created_at), uuid.UUID(row_id)
    except (ValueError, binascii.Error) as exc:
        raise ValidationFailedError("Invalid cursor") from exc
