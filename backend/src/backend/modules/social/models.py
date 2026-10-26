"""Social accounts the admins connected, and the posts queued for them.

These belong to Rolesetu itself, not to any user, so they are reached only
through admin routes.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, IdMixin, TimestampMixin


class SocialAccount(IdMixin, TimestampMixin, Base):
    """A LinkedIn profile, Facebook Page or Instagram business account we can post to."""

    __tablename__ = "social_accounts"
    __table_args__ = (
        Index("ix_social_accounts_platform_external", "platform", "external_id", unique=True),
    )

    # "linkedin" | "facebook" | "instagram"
    platform: Mapped[str] = mapped_column(String(20))
    # LinkedIn member id, Facebook Page id or Instagram account id.
    external_id: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    # Encrypted with core/encryption. Never returned by the API.
    access_token: Mapped[str] = mapped_column(Text)
    # None when the platform's token does not expire (Facebook Page tokens).
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    connected_by: Mapped[str] = mapped_column(String(320))
    # "active", or "expired" once the platform refuses the token.
    status: Mapped[str] = mapped_column(String(20), default="active")


class SocialPost(IdMixin, TimestampMixin, Base):
    """One post, written once and sent to one or more accounts.

    A post starts as a draft. Nothing is published until an admin schedules it
    (for a time, or now). That step is the approval.
    """

    __tablename__ = "social_posts"
    __table_args__ = (
        Index("ix_social_posts_status_scheduled", "status", "scheduled_at"),
        Index("ix_social_posts_created", "created_at", "id"),
    )

    text: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(2000), default=None)
    # "draft" | "scheduled" | "publishing" | "posted" | "partly_posted" | "failed"
    status: Mapped[str] = mapped_column(String(20), default="draft")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_by: Mapped[str] = mapped_column(String(320))
    approved_by: Mapped[str | None] = mapped_column(String(320), default=None)


class SocialPostTarget(IdMixin, TimestampMixin, Base):
    """Where one post goes, and what happened when it was sent there."""

    __tablename__ = "social_post_targets"
    __table_args__ = (Index("ix_social_post_targets_post", "post_id"),)

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("social_posts.id", ondelete="CASCADE")
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    # "pending" | "publishing" | "posted" | "failed"
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    external_url: Mapped[str | None] = mapped_column(String(2000), default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
