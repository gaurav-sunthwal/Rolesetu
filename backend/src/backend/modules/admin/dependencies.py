from dataclasses import dataclass

from fastapi import Depends

from backend.core.config import get_settings
from backend.core.exceptions import ForbiddenError
from backend.core.security import CurrentUser, require_dashboard_session


@dataclass(frozen=True)
class Admin:
    email: str


async def get_admin(current_user: CurrentUser = Depends(require_dashboard_session)) -> Admin:
    """The signed-in admin. Every admin route depends on this.

    An admin is a Google account whose verified email is listed in
    ADMIN_EMAILS. The list is read on every request, so removing an address
    locks that person out straight away. With the list empty, nobody is one.
    """
    email = (current_user.email or "").lower()
    allowed = {address.lower() for address in get_settings().admin_emails}
    if not email or not current_user.email_verified or email not in allowed:
        raise ForbiddenError("This account is not an admin.")
    return Admin(email=email)
