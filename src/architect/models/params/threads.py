"""Thread-domain parameter models (create / archive / lock / unarchive)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ThreadType = Literal["public", "private"]
AutoArchive = Literal[60, 1440, 4320, 10080]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateThreadParams(_Strict):
    """Create a thread inside an existing text or forum channel."""

    parent_channel: str = Field(description="Parent channel name or ID")
    name: str = Field(description="Thread name, max 100 chars")
    type: ThreadType = Field(
        default="public",
        description="'public' visible to everyone, 'private' invite-only",
    )
    auto_archive_minutes: AutoArchive | None = Field(
        default=None,
        description="Auto-archive duration in minutes (60, 1440, 4320, 10080)",
    )
    reason: str | None = Field(default=None, description="Audit-log reason")


class ArchiveThreadParams(_Strict):
    """Archive an active thread."""

    thread: str = Field(description="Thread name or ID")
    reason: str | None = Field(default=None, description="Audit-log reason")


class UnarchiveThreadParams(_Strict):
    """Reopen an archived thread."""

    thread: str = Field(description="Thread name or ID")
    reason: str | None = Field(default=None, description="Audit-log reason")


class LockThreadParams(_Strict):
    """Lock a thread (no further messages, but still readable)."""

    thread: str = Field(description="Thread name or ID")
    reason: str | None = Field(default=None, description="Audit-log reason")
