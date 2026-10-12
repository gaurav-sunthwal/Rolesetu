"""Works out who is calling the API. The dashboard signs in with Firebase Auth
and sends its ID token; the browser extension sends a key issued from Settings.
"""

from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import ForbiddenError, UnauthorizedError
from backend.core.firebase_tokens import InvalidTokenError, verify_id_token
from backend.db.session import get_db
from backend.modules.extension import service as extension_service

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    uid: str
    email: str | None
    # True when the request was signed with a browser-extension key, not a
    # dashboard sign-in. Such requests are only allowed on a few routes.
    via_extension: bool = False


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """Who is calling: a dashboard session (Firebase ID token) or the user's
    browser extension (a key issued from Settings).
    """
    if credentials is None:
        raise UnauthorizedError("Missing bearer token")
    token = credentials.credentials

    if token.startswith(extension_service.TOKEN_PREFIX):
        user = await extension_service.user_for_token(db, token)
        if user is None:
            raise UnauthorizedError(
                "This browser extension is no longer connected. Connect it again from Settings."
            )
        return CurrentUser(uid=user.firebase_uid, email=user.email, via_extension=True)

    try:
        decoded = await verify_id_token(token)
    except InvalidTokenError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc

    return CurrentUser(uid=decoded["uid"], email=decoded.get("email"))


async def require_dashboard_session(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """For everything the extension has no business doing (keys, account, files)."""
    if current_user.via_extension:
        raise ForbiddenError("This can only be done from the Rolesetu dashboard.")
    return current_user
