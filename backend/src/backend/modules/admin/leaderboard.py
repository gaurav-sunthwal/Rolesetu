"""The most active users, and which features each of them uses most.

Every feature is counted from the table that already records it (job checks,
applications, AI calls, extension events...), so nothing new is written to track
usage. One query counts every user's actions per feature over the period, and the
days they were active; a second loads the profiles of the top users only.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai.answer_writer import PURPOSE as AI_ANSWER_PURPOSE


class Feature(BaseModel):
    key: str
    label: str
    surface: Literal["dashboard", "extension", "ai", "inbox"]


# The order is the order the admin page lists them in.
FEATURES: list[Feature] = [
    Feature(key="job_check", label="Job checks", surface="dashboard"),
    Feature(key="extension_score", label="Scores on job sites", surface="extension"),
    Feature(key="autofill", label="Autofill", surface="extension"),
    Feature(key="suggestion_used", label="Saved answers reused", surface="extension"),
    Feature(key="answer_saved", label="Answers saved", surface="extension"),
    Feature(key="ai_answer", label="AI answers", surface="ai"),
    Feature(key="resume_assistant", label="Resume assistant", surface="ai"),
    Feature(key="application", label="Applications tracked", surface="dashboard"),
    Feature(key="email_tracked", label="Job emails tracked", surface="inbox"),
    Feature(key="share", label="Score cards shared", surface="dashboard"),
    Feature(key="resume_upload", label="Resume uploads", surface="dashboard"),
]
_KEYS = {feature.key for feature in FEATURES}

# Extension events that are features, by the name the extension sends.
_EXTENSION_EVENTS = {
    "job_scored": "extension_score",
    "autofill_filled": "autofill",
    "suggestion_used": "suggestion_used",
    "answer_saved": "answer_saved",
}
_AI_PURPOSES = {AI_ANSWER_PURPOSE: "ai_answer", "resume-assistant": "resume_assistant"}


def _case(column: str, mapping: dict[str, str]) -> str:
    # The values are constants from this file, never input, so they are inlined.
    whens = " ".join(f"WHEN '{name}' THEN '{key}'" for name, key in mapping.items())
    return f"CASE {column} {whens} END"


_ACTIONS = f"""
WITH acts AS (
    SELECT user_id, 'job_check' AS feature, created_at FROM matches WHERE created_at >= :since
    UNION ALL
    SELECT user_id, 'application', created_at FROM applications WHERE created_at >= :since
    UNION ALL
    SELECT user_id, {_case("name", _EXTENSION_EVENTS)}, created_at FROM ext_events
     WHERE created_at >= :since AND name IN ({", ".join(f"'{n}'" for n in _EXTENSION_EVENTS)})
    UNION ALL
    SELECT user_id, {_case("purpose", _AI_PURPOSES)}, created_at FROM ai_calls
     WHERE created_at >= :since AND ok AND user_id IS NOT NULL
       AND purpose IN ({", ".join(f"'{p}'" for p in _AI_PURPOSES)})
    UNION ALL
    SELECT user_id, 'email_tracked', created_at FROM email_messages WHERE created_at >= :since
    UNION ALL
    SELECT user_id, 'share', created_at FROM match_shares WHERE created_at >= :since
    UNION ALL
    SELECT user_id, 'resume_upload', created_at FROM resume_files WHERE created_at >= :since
)
SELECT user_id,
       feature,
       GROUPING(feature) = 1 AS is_total,
       count(*) AS actions,
       max(created_at) AS last_at,
       count(DISTINCT (created_at AT TIME ZONE 'UTC')::date) AS active_days
FROM acts
GROUP BY GROUPING SETS ((user_id, feature), (user_id))
"""

_PROFILES = text(
    """
    SELECT u.id, u.email, u.name, u.created_at,
           p.full_name, p.headline, p.location,
           EXISTS (SELECT 1 FROM resume_files r WHERE r.user_id = u.id) AS has_resume,
           EXISTS (SELECT 1 FROM extension_tokens t WHERE t.user_id = u.id) AS has_extension,
           EXISTS (SELECT 1 FROM integrations i WHERE i.user_id = u.id) AS has_gmail,
           EXISTS (
               SELECT 1 FROM billing_orders b
               WHERE b.user_id = u.id AND b.status = 'paid'
                 AND b.pro_starts_at <= now() AND b.pro_ends_at > now()
           ) AS is_pro
    FROM users u
    LEFT JOIN profiles p ON p.user_id = u.id
    WHERE u.id = ANY(:ids)
    """
)


class LeaderRow(BaseModel):
    rank: int
    user_id: uuid.UUID
    email: str
    name: str | None
    headline: str | None
    location: str | None
    joined_at: datetime
    last_active_at: datetime
    plan: Literal["free", "pro"]
    has_resume: bool
    extension_connected: bool
    gmail_connected: bool
    total_actions: int
    active_days: int
    # Actions per feature key, only features used at least once.
    features: dict[str, int]
    # The feature keys this user uses most, most first.
    top_features: list[str]


class Leaderboard(BaseModel):
    period_days: int | None
    features: list[Feature]
    # Every user's actions per feature over the period, for the "who uses what" mix.
    totals: dict[str, int]
    active_users: int
    users: list[LeaderRow]


async def leaderboard(db: AsyncSession, *, days: int | None, limit: int) -> Leaderboard:
    now = datetime.now(UTC)
    since = now - timedelta(days=days) if days else datetime(2000, 1, 1, tzinfo=UTC)
    rows = (await db.execute(text(_ACTIONS), {"since": since})).all()

    per_user: dict[uuid.UUID, dict[str, int]] = {}
    summary: dict[uuid.UUID, tuple[int, datetime, int]] = {}
    totals: dict[str, int] = {}
    for user_id, feature, is_total, actions, last_at, active_days in rows:
        if is_total:
            summary[user_id] = (int(actions), last_at, int(active_days))
        elif feature in _KEYS:
            per_user.setdefault(user_id, {})[feature] = int(actions)
            totals[feature] = totals.get(feature, 0) + int(actions)

    ranked = sorted(summary.items(), key=lambda item: (item[1][0], item[1][1]), reverse=True)
    top = ranked[:limit]
    profiles = {
        row.id: row
        for row in (await db.execute(_PROFILES, {"ids": [user_id for user_id, _ in top]})).all()
    }

    users: list[LeaderRow] = []
    for position, (user_id, (total, last_at, active_days)) in enumerate(top, start=1):
        profile = profiles.get(user_id)
        if profile is None:  # deleted between the two queries
            continue
        used = per_user.get(user_id, {})
        users.append(
            LeaderRow(
                rank=position,
                user_id=user_id,
                email=profile.email,
                name=profile.full_name or profile.name,
                headline=profile.headline,
                location=profile.location,
                joined_at=profile.created_at,
                last_active_at=last_at,
                plan="pro" if profile.is_pro else "free",
                has_resume=profile.has_resume,
                extension_connected=profile.has_extension,
                gmail_connected=profile.has_gmail,
                total_actions=total,
                active_days=active_days,
                features=used,
                top_features=[key for key, _ in sorted(used.items(), key=lambda kv: -kv[1])][:3],
            )
        )
    return Leaderboard(
        period_days=days,
        features=FEATURES,
        totals=totals,
        active_users=len(summary),
        users=users,
    )
