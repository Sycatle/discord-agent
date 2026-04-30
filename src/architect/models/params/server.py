"""Server settings and welcome screen parameter models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VerificationLevel = Literal["none", "low", "medium", "high", "highest"]
NotificationLevel = Literal["all_messages", "only_mentions"]
ContentFilterLevel = Literal["disabled", "members_without_roles", "all_members"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EditServerParams(_Strict):
    """Edit Discord server settings (verification level, filters, system channels, locale, etc.)."""

    name: str | None = Field(default=None, description="New server name (optional)")
    verification_level: VerificationLevel | None = Field(
        default=None,
        description="Verification level for new members (optional)",
    )
    default_message_notifications: NotificationLevel | None = Field(
        default=None,
        description="Default notifications for new members (optional)",
    )
    explicit_content_filter: ContentFilterLevel | None = Field(
        default=None, description="Explicit content filter level (optional)"
    )
    afk_channel: str | None = Field(
        default=None,
        description="AFK voice channel name or ID, null to disable (optional)",
    )
    afk_timeout: int | None = Field(default=None, description="AFK delay in seconds (optional)")
    system_channel: str | None = Field(
        default=None,
        description=("Channel name or ID for system messages (welcome, boosts) (optional)"),
    )
    rules_channel: str | None = Field(
        default=None,
        description="Rules channel name or ID (community servers) (optional)",
    )
    public_updates_channel: str | None = Field(
        default=None,
        description=("Channel name or ID for Discord updates (community servers) (optional)"),
    )
    safety_alerts_channel: str | None = Field(
        default=None,
        description="Channel name or ID for Discord safety alerts (optional)",
    )
    description: str | None = Field(
        default=None, description="Community server description (optional)"
    )
    preferred_locale: str | None = Field(
        default=None,
        description="Preferred locale, e.g. 'fr', 'en-US', 'de' (optional)",
    )
    premium_progress_bar_enabled: bool | None = Field(
        default=None,
        description="Show the boost progress bar (optional)",
    )
    community: bool | None = Field(
        default=None,
        description="Toggle community mode (requires rules + updates channels)",
    )


class WelcomeChannelEntry(_Strict):
    """A single entry in the welcome screen channel list."""

    channel: str = Field(description="Channel name or ID")
    description: str = Field(description="Description shown next to the channel")
    emoji: str | None = Field(default=None, description="Emoji prefix (optional)")


class EditWelcomeScreenParams(_Strict):
    """Edit the welcome screen of a community server."""

    enabled: bool | None = Field(default=None, description="Enable the welcome screen (optional)")
    description: str | None = Field(default=None, description="Welcome text shown (optional)")
    welcome_channels: list[WelcomeChannelEntry] | None = Field(
        default=None,
        description="Channels surfaced on the welcome screen (optional)",
    )
