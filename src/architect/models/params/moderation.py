"""Moderation parameter models (ban / kick / unban / bulk-timeout)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BanMemberParams(_Strict):
    """Permanently ban a member. IRREVERSIBLE without unban."""

    member: str = Field(description="@mention or numeric user_id")
    delete_message_days: int = Field(
        default=0,
        ge=0,
        le=7,
        description="Days of recent messages to delete (0-7)",
    )
    reason: str | None = Field(default=None, description="Audit-log reason")


class KickMemberParams(_Strict):
    """Kick a member from the server. Member can rejoin via invite."""

    member: str = Field(description="@mention or numeric user_id")
    reason: str | None = Field(default=None, description="Audit-log reason")


class UnbanMemberParams(_Strict):
    """Lift a ban so the user can rejoin via an invite."""

    user_id: str = Field(description="Numeric user_id of the banned user")
    reason: str | None = Field(default=None, description="Audit-log reason")


class BulkTimeoutMembersParams(_Strict):
    """Timeout up to 50 members in one action (sequential, with backoff).

    Discord has no native bulk-timeout endpoint; the handler iterates
    over the targets. Use this only when you really need to silence many
    members at once (e.g. raid response).
    """

    members: list[str] = Field(
        description="@mentions or numeric user_ids (max 50)",
        max_length=50,
    )
    duration_minutes: int = Field(
        ge=1,
        le=40320,  # 28 days in minutes
        description="Timeout duration in minutes (1-40320, max 28 days)",
    )
    reason: str | None = Field(default=None, description="Audit-log reason")
