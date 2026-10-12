"""Works out which tracked application a mail is about, and what the mail
does to that application's status. When it cannot be sure, it says so and the
mail goes to the user's Review list instead of being guessed at.
"""

import re
from collections.abc import Sequence
from typing import Literal, Protocol

Outcome = Literal["none", "ambiguous"]

# What each kind of mail means for an application. An assessment is a reply.
STATUS_FOR_KIND = {
    "applied": "applied",
    "rejected": "rejected",
    "interview": "interview",
    "assessment": "replied",
    "offer": "offer",
}
_RANK = {"saved": 0, "applied": 1, "replied": 2, "interview": 3, "offer": 4}
_COMPANY_FILLER = re.compile(
    r"\b(?:pvt|private|ltd|limited|inc|llc|llp|corp|corporation|gmbh|co|company|the|"
    r"technologies|technology|tech|labs?|software|solutions|systems|services|india|global|group)\b",
    re.IGNORECASE,
)
_ROLE_FILLER = frozenset({"the", "a", "an", "of", "and", "for", "in", "at", "i", "ii", "iii"})


class Tracked(Protocol):
    """The parts of an application this file reads."""

    company: str
    role: str
    status: str


def company_key(name: str) -> str:
    """ "Acme Technologies Pvt. Ltd." and "ACME" both become "acme"."""
    return re.sub(r"[^a-z0-9]+", "", _COMPANY_FILLER.sub(" ", name).lower())


def same_company(first: str, second: str) -> bool:
    a, b = company_key(first), company_key(second)
    if not a or not b:
        return False
    # "Razorpay" and "Razorpay Software" are one company; "Go" and "Google" are not.
    return a == b or (min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)))


def _role_words(role: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9+#.]+", role.lower()) if word not in _ROLE_FILLER}


def role_overlap(first: str, second: str) -> float:
    a, b = _role_words(first), _role_words(second)
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def find_application[T: Tracked](
    applications: Sequence[T],
    company: str | None,
    role: str | None,
    *,
    new_application: bool = False,
    unnamed_role: str = "",
) -> T | Outcome:
    """The application this mail belongs to, "none" if the user tracks nothing
    like it, or "ambiguous" when several fit and the role does not settle it.

    `new_application` says the mail confirms a fresh application. For those, a
    clearly different role at a company already tracked is a second application,
    not news about the first. `unnamed_role` is the placeholder used when an
    earlier mail did not name the role.
    """
    if not company:
        return "ambiguous"
    at_company = [item for item in applications if same_company(item.company, company)]
    if not at_company:
        return "none"
    if len(at_company) == 1:
        only = at_company[0]
        different = (
            role is not None and only.role != unnamed_role and role_overlap(only.role, role) == 0
        )
        return "none" if new_application and different else only
    if role:
        ranked = sorted(at_company, key=lambda item: -role_overlap(item.role, role))
        best, runner_up = role_overlap(ranked[0].role, role), role_overlap(ranked[1].role, role)
        if best >= 0.5 and best > runner_up:
            return ranked[0]
    return "ambiguous"


def next_status(current: str, kind: str) -> str | None:
    """The status the application should move to, or None to leave it alone.
    A status never moves backwards: an "application received" mail that turns
    up late does not undo an interview.
    """
    target = STATUS_FOR_KIND.get(kind)
    if target is None or target == current:
        return None
    if target == "rejected":
        return None if current == "offer" else target
    if current == "rejected":
        # Mails are read oldest first, so this one came after the rejection.
        return target if target in ("interview", "offer") else None
    return target if _RANK[target] > _RANK.get(current, 0) else None
