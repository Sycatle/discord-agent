"""Channel-related parameter models (text, voice, forum, stage, invites, webhooks)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ForumSortOrder = Literal["latest_activity", "creation_date"]
ForumLayout = Literal["list", "gallery"]
VideoQualityMode = Literal["auto", "full"]
AutoArchiveDuration = Literal[60, 1440, 4320, 10080]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateCategoryParams(_Strict):
    """Create a Discord category in the guild."""

    name: str = Field(description="Category name")


class CreateTextChannelParams(_Strict):
    """Create a text channel, optionally inside a category."""

    name: str = Field(description="Channel name")
    category: str | None = Field(default=None, description="Parent category name (optional)")


class CreateVoiceChannelParams(_Strict):
    """Create a voice channel, optionally inside a category."""

    name: str = Field(description="Voice channel name")
    category: str | None = Field(default=None, description="Parent category name (optional)")


class CreateForumChannelParams(_Strict):
    """Create a Discord forum channel (threads with tags)."""

    name: str = Field(description="Forum name")
    category: str | None = Field(default=None, description="Parent category (optional)")
    topic: str | None = Field(
        default=None, description="Forum description, max 4096 chars (optional)"
    )
    slowmode: int | None = Field(
        default=None,
        ge=0,
        le=21600,
        description="Per-user message delay in seconds, 0-21600 (optional)",
    )
    nsfw: bool | None = Field(default=None, description="Adult content flag (optional)")
    available_tags: list[str] | None = Field(
        default=None,
        max_length=20,
        description="Available tag names, max 20 (optional)",
    )
    require_tag: bool | None = Field(
        default=None, description="Require a tag on each thread (optional)"
    )
    default_sort_order: ForumSortOrder | None = Field(
        default=None, description="Thread sort order (optional)"
    )
    default_forum_layout: ForumLayout | None = Field(
        default=None, description="Default forum layout (optional)"
    )


class CreateStageChannelParams(_Strict):
    """Create a Stage channel (conferences/podcasts)."""

    name: str = Field(description="Stage name")
    category: str | None = Field(default=None, description="Parent category (optional)")
    bitrate: int | None = Field(default=None, description="Audio quality in bps (optional)")
    user_limit: int | None = Field(
        default=None, ge=0, le=10000, description="User limit 0-10000 (optional)"
    )
    rtc_region: str | None = Field(
        default=None, description="Voice region override, null = auto (optional)"
    )
    position: int | None = Field(default=None, description="Position in the list (optional)")


class EditChannelParams(_Strict):
    """Edit an existing channel or category (rename, topic, slowmode, nsfw, position, bitrate, etc.)."""

    channel: str = Field(description="Channel name or ID")
    name: str | None = Field(default=None, description="New name (optional)")
    topic: str | None = Field(default=None, description="Channel topic, max 1024 chars (optional)")
    slowmode: int | None = Field(
        default=None,
        ge=0,
        le=21600,
        description="Slowmode delay in seconds, 0-21600 (optional)",
    )
    nsfw: bool | None = Field(default=None, description="Adult content flag (optional)")
    position: int | None = Field(default=None, description="Position in the list (optional)")
    bitrate: int | None = Field(
        default=None,
        description="Audio quality in bps, voice/stage only (optional)",
    )
    user_limit: int | None = Field(
        default=None,
        ge=0,
        le=99,
        description="Member limit, voice: 0-99 (optional)",
    )
    parent_id: str | None = Field(
        default=None,
        description="Move to this category (name or ID) (optional)",
    )
    rtc_region: str | None = Field(default=None, description="Voice region override (optional)")
    video_quality_mode: VideoQualityMode | None = Field(
        default=None, description="Voice/stage video quality (optional)"
    )
    default_auto_archive_duration: AutoArchiveDuration | None = Field(
        default=None, description="Thread auto-archive duration in minutes (optional)"
    )


class DeleteChannelParams(_Strict):
    """Permanently delete a channel or category. IRREVERSIBLE."""

    channel: str = Field(description="Channel name or ID to delete")
    reason: str | None = Field(default=None, description="Deletion reason (optional)")


class SetChannelPermissionsParams(_Strict):
    """Set channel permissions for a role."""

    channel: str = Field(description="Channel name")
    role: str = Field(description="Role name")
    allow: list[str] | None = Field(default=None, description="Permissions to allow (optional)")
    deny: list[str] | None = Field(default=None, description="Permissions to deny (optional)")


class CreateInviteParams(_Strict):
    """Create an invite link for a channel."""

    channel: str = Field(description="Channel name or ID")
    max_age: int | None = Field(
        default=None,
        ge=0,
        le=604800,
        description="Validity in seconds, 0 = permanent, max 604800 (optional)",
    )
    max_uses: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Max uses, 0 = unlimited, max 100 (optional)",
    )
    temporary: bool | None = Field(default=None, description="Kick if no role assigned (optional)")


class DeleteInviteParams(_Strict):
    """Revoke an invite link by its code."""

    code: str = Field(description="Invite code (e.g. 'xKy3h2')")


class CreateWebhookParams(_Strict):
    """Create an incoming webhook on a channel."""

    channel: str = Field(description="Channel name or ID")
    name: str = Field(description="Webhook name")


class EditWebhookParams(_Strict):
    """Rename a webhook or move it to another channel."""

    webhook: str = Field(description="Webhook name or ID")
    name: str | None = Field(default=None, description="New name (optional)")
    channel: str | None = Field(
        default=None, description="Move to this channel (name or ID) (optional)"
    )


class DeleteWebhookParams(_Strict):
    """Delete a webhook."""

    webhook: str = Field(description="Webhook name or ID")
