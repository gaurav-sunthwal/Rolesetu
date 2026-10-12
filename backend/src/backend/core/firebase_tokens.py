"""Checks a Firebase sign-in token using Google's public keys.

No credential is needed for this: the token is signed by Google, and the keys
to check that signature are published. That matters because a server has no
Google login of its own, while a developer's laptop often does, so a check that
quietly relies on one works locally and fails once deployed.
"""

import re
import time
from typing import Any

import httpx
from google.auth import exceptions as google_exceptions
from google.auth import jwt

from backend.core.config import get_settings

_KEYS_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
)
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
# Used when Google's reply does not say how long its keys may be kept.
_DEFAULT_KEEP_SECONDS = 3600

_keys: dict[str, str] = {}
_keys_expire_at = 0.0


class InvalidTokenError(Exception):
    pass


async def _public_keys() -> dict[str, str]:
    """Google's current signing keys. Kept for as long as Google says they are
    valid, so most requests make no network call at all.
    """
    global _keys, _keys_expire_at  # noqa: PLW0603 - a small process-wide cache of public data
    if _keys and time.time() < _keys_expire_at:
        return _keys
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.get(_KEYS_URL)
    response.raise_for_status()
    max_age = re.search(r"max-age=(\d+)", response.headers.get("cache-control", ""))
    _keys = response.json()
    _keys_expire_at = time.time() + (int(max_age.group(1)) if max_age else _DEFAULT_KEEP_SECONDS)
    return _keys


async def verify_id_token(token: str) -> dict[str, Any]:
    """Returns the token's contents if Google signed it for this project and it
    has not expired. Raises InvalidTokenError otherwise.
    """
    project_id = get_settings().firebase_project_id
    if not project_id:
        raise InvalidTokenError("FIREBASE_PROJECT_ID is not set")
    try:
        keys = await _public_keys()
        # Checks the signature, the expiry and that the token was issued for this project.
        claims: dict[str, Any] = jwt.decode(token, certs=keys, audience=project_id)  # type: ignore[no-untyped-call]
    except (ValueError, google_exceptions.GoogleAuthError, httpx.HTTPError) as exc:
        raise InvalidTokenError(str(exc)) from exc
    if claims.get("iss") != f"https://securetoken.google.com/{project_id}":
        raise InvalidTokenError("Token was not issued by this project's sign-in service")
    if not claims.get("sub"):
        raise InvalidTokenError("Token names no user")
    return {**claims, "uid": claims["sub"]}
