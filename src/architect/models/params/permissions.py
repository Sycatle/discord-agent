"""Granular permission-override parameter models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TargetType = Literal["role", "member"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SetChannelPermissionOverridesParams(_Strict):
    """Set a granular permission override (allow + deny) on a channel.

    Use this when `set_channel_permissions` is too coarse — supports
    member-level overrides AND mixed allow/deny lists in a single call.
    Permission flags must be valid attributes of `discord.Permissions`
    (e.g. 'view_channel', 'send_messages', 'manage_messages').
    """

    channel: str = Field(description="Channel name or ID")
    target_type: TargetType = Field(
        description="'role' or 'member' — the kind of override"
    )
    target: str = Field(
        description="Role name / @mention / numeric ID of the target"
    )
    allow: list[str] = Field(
        default_factory=list,
        description="Permissions explicitly allowed",
    )
    deny: list[str] = Field(
        default_factory=list,
        description="Permissions explicitly denied",
    )
    reason: str | None = Field(default=None, description="Audit-log reason")
