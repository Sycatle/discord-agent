"""Member-related parameter models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EditMemberParams(BaseModel):
    """Edit a member: nickname, server mute/deafen, timeout, move to a voice channel."""

    model_config = ConfigDict(extra="forbid")

    user: str = Field(description="@mention or numeric user_id")
    nick: str | None = Field(default=None, description="New nickname, null to reset (optional)")
    mute: bool | None = Field(default=None, description="Server mute the member (optional)")
    deaf: bool | None = Field(default=None, description="Server deafen the member (optional)")
    timeout_until: str | None = Field(
        default=None,
        description=("ISO8601 UTC datetime until the timeout lasts, null to remove (optional)"),
    )
    move_to_channel: str | None = Field(
        default=None,
        description="Voice channel name or ID to move the member to (optional)",
    )
