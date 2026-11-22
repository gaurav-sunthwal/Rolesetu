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
    # Last read from the platform with the post numbers (Instagram and YouTube).
    followers: Mapped[int | None] = mapped_column(Integer, default=None)


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

    # The caption (Instagram, Facebook) or the whole post (LinkedIn).
    text: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(2000), default=None)
    # A reel: the mp4's key in R2 (social/videos/...). A post has an image or a video.
    video_key: Mapped[str | None] = mapped_column(String(200), default=None)
    # YouTube has its own title (100 characters) and description.
    youtube_title: Mapped[str | None] = mapped_column(String(100), default=None)
    youtube_description: Mapped[str | None] = mapped_column(Text, default=None)
    # A frame of the reel, made in the browser at upload, for lists and the stats table.
    thumbnail_url: Mapped[str | None] = mapped_column(String(2000), default=None)
    # "draft" | "scheduled" | "publishing" | "posted" | "partly_posted" | "failed"
    status: Mapped[str] = mapped_column(String(20), default="draft")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_by: Mapped[str] = mapped_column(String(320))
    approved_by: Mapped[str | None] = mapped_column(String(320), default=None)


class SocialPostTarget(IdMixin, TimestampMixin, Base):
    """Where one post goes, and what happened when it was sent there."""

    __tablename__ = "social_post_targets"
    __table_args__ = (
        Index("ix_social_post_targets_post", "post_id"),
        Index("ix_social_post_targets_status_posted", "status", "posted_at"),
    )

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
    # The platform's id for the post, used to read its numbers later.
    external_id: Mapped[str | None] = mapped_column(String(100), default=None)
    # The post's numbers, refreshed every few hours for its first 30 days.
    # None: the platform does not report it (or has not yet).
    views: Mapped[int | None] = mapped_column(Integer, default=None)
    reach: Mapped[int | None] = mapped_column(Integer, default=None)
    likes: Mapped[int | None] = mapped_column(Integer, default=None)
    comments: Mapped[int | None] = mapped_column(Integer, default=None)
    shares: Mapped[int | None] = mapped_column(Integer, default=None)
    saves: Mapped[int | None] = mapped_column(Integer, default=None)
    # Instagram's average watch time per view, in milliseconds.
    avg_watch_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    metrics_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class SocialMetricSnapshot(IdMixin, TimestampMixin, Base):
    """One reading of a posted target's numbers. Kept so the admin panel can show
    what changed in the last 24 hours, and since the previous reading."""

    __tablename__ = "social_metric_snapshots"
    __table_args__ = (Index("ix_social_metric_snapshots_target_taken", "target_id", "taken_at"),)

    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("social_post_targets.id", ondelete="CASCADE")
    )
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    views: Mapped[int | None] = mapped_column(Integer, default=None)
    likes: Mapped[int | None] = mapped_column(Integer, default=None)
    comments: Mapped[int | None] = mapped_column(Integer, default=None)
    shares: Mapped[int | None] = mapped_column(Integer, default=None)
