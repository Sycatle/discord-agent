"""Scheduled event parameter models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EntityType = Literal["voice", "stage", "external"]
EventStatus = Literal["active", "completed", "canceled"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateScheduledEventParams(_Strict):
    """Create a Discord scheduled event (voice, stage, or external)."""

    name: str = Field(description="Event title")
    start_time: str = Field(description="ISO8601 UTC start, e.g. '2026-05-01T18:00:00Z'")
    end_time: str | None = Field(
        default=None,
        description="ISO8601 UTC end (required for external, optional otherwise)",
    )
    entity_type: EntityType = Field(
        description="Type: 'voice' (voice channel), 'stage' (stage), 'external' (physical location)"
    )
    channel: str | None = Field(
        default=None,
        description="Voice/stage channel name or ID (required for voice/stage)",
    )
    location: str | None = Field(
        default=None, description="Physical location (required for 'external')"
    )
    description: str | None = Field(default=None, description="Event description (optional)")


class EditScheduledEventParams(_Strict):
    """Edit a scheduled event or change its status."""

    event: str = Field(description="Event name or ID")
    name: str | None = Field(default=None, description="New name (optional)")
    description: str | None = Field(default=None, description="New description (optional)")
    start_time: str | None = Field(default=None, description="New ISO8601 start time (optional)")
    end_time: str | None = Field(default=None, description="New ISO8601 end time (optional)")
    status: EventStatus | None = Field(default=None, description="New status (optional)")


class DeleteScheduledEventParams(_Strict):
    """Delete a scheduled event."""

    event: str = Field(description="Event name or ID")
