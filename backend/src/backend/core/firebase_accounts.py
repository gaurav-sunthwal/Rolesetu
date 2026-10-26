"""Removes a person's Firebase sign-in, so a deleted account leaves nothing behind.

This needs a Firebase service account key (FIREBASE_SERVICE_ACCOUNT_JSON, or
a file at FIREBASE_SERVICE_ACCOUNT_PATH). Without one, deleting an account
still removes all of Rolesetu's data and says the sign-in must be removed by
hand in the Firebase console.
"""

import asyncio
import json
import logging
from functools import lru_cache

import firebase_admin
from firebase_admin import auth, credentials

from backend.core.config import get_settings

logger = logging.getLogger(__name__)

_APP_NAME = "rolesetu-accounts"
_TIMEOUT_SECONDS = 10.0


class SignInNotRemovableError(Exception):
    """The sign-in could not be removed. The message says why, for an admin."""


def is_configured() -> bool:
    settings = get_settings()
    return bool(settings.firebase_service_account_json or settings.firebase_service_account_path)


@lru_cache
def _app() -> firebase_admin.App:
    settings = get_settings()
    if settings.firebase_service_account_json:
        key = credentials.Certificate(json.loads(settings.firebase_service_account_json))
    elif settings.firebase_service_account_path:
        key = credentials.Certificate(settings.firebase_service_account_path)
    else:
        raise SignInNotRemovableError("No Firebase service account key is set on the server.")
    # Its own named app, so nothing else in the process can pick up this key by accident.
    return firebase_admin.initialize_app(key, name=_APP_NAME)


def _delete(uid: str) -> None:
    try:
        auth.delete_user(uid, app=_app())
    except auth.UserNotFoundError:
        return  # Already gone, which is the outcome we want.


async def delete_sign_in(uid: str) -> None:
    """Deletes the Firebase user with this uid, or raises SignInNotRemovableError."""
    if not is_configured():
        raise SignInNotRemovableError("No Firebase service account key is set on the server.")
    try:
        await asyncio.wait_for(asyncio.to_thread(_delete, uid), timeout=_TIMEOUT_SECONDS)
    except SignInNotRemovableError:
        raise
    except TimeoutError as exc:
        raise SignInNotRemovableError("Firebase did not answer in time.") from exc
    except Exception as exc:
        logger.warning("Removing Firebase sign-in uid=%s failed: %s", uid, type(exc).__name__)
        raise SignInNotRemovableError("Firebase refused the request.") from exc
