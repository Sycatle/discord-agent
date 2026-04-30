"""Coverage for scheduled-event handlers."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from architect.executor.handlers.events import (
    create_scheduled_event,
    delete_scheduled_event,
    edit_scheduled_event,
)
from architect.models.params.events import (
    CreateScheduledEventParams,
    DeleteScheduledEventParams,
    EditScheduledEventParams,
)


def _guild_with_channels() -> MagicMock:
    guild = MagicMock(spec=discord.Guild)
    voice = MagicMock()
    voice.name = "voice-room"
    voice.id = 1
    guild.channels = [voice]
    guild.get_channel = MagicMock(return_value=None)
    event = MagicMock()
    event.name = "Game Night"
    event.id = 99
    event.edit = AsyncMock()
    event.delete = AsyncMock()
    guild.scheduled_events = [event]
    created = MagicMock(name="created")
    created.name = "Game Night"
    guild.create_scheduled_event = AsyncMock(return_value=created)
    return guild


@pytest.mark.asyncio
async def test_create_external_event_with_location():
    guild = _guild_with_channels()
    params = CreateScheduledEventParams(
        name="Meetup",
        start_time="2026-05-01T18:00:00+00:00",
        end_time="2026-05-01T20:00:00+00:00",
        entity_type="external",
        location="The Grand Hall",
        description="A meetup",
    )
    result = await create_scheduled_event(params, guild)
    assert "created" in result.lower()
    guild.create_scheduled_event.assert_called_once()


@pytest.mark.asyncio
async def test_create_external_event_without_location_raises():
    guild = _guild_with_channels()
    params = CreateScheduledEventParams(
        name="Meetup",
        start_time="2026-05-01T18:00:00+00:00",
        entity_type="external",
    )
    with pytest.raises(ValueError, match="require a location"):
        await create_scheduled_event(params, guild)


@pytest.mark.asyncio
async def test_create_voice_event_without_channel_raises():
    guild = _guild_with_channels()
    params = CreateScheduledEventParams(
        name="x",
        start_time="2026-05-01T18:00:00+00:00",
        entity_type="voice",
    )
    with pytest.raises(ValueError, match="require a channel"):
        await create_scheduled_event(params, guild)


@pytest.mark.asyncio
async def test_create_voice_event_unknown_channel_raises():
    guild = _guild_with_channels()
    params = CreateScheduledEventParams(
        name="x",
        start_time="2026-05-01T18:00:00+00:00",
        entity_type="voice",
        channel="ghost",
    )
    with pytest.raises(ValueError, match="Channel not found"):
        await create_scheduled_event(params, guild)


@pytest.mark.asyncio
async def test_create_voice_event_with_known_channel():
    guild = _guild_with_channels()
    params = CreateScheduledEventParams(
        name="Game Night",
        start_time="2026-05-01T18:00:00+00:00",
        entity_type="voice",
        channel="voice-room",
    )
    await create_scheduled_event(params, guild)
    kwargs = guild.create_scheduled_event.call_args.kwargs
    assert kwargs["channel"].name == "voice-room"


@pytest.mark.asyncio
async def test_edit_scheduled_event_full_payload():
    guild = _guild_with_channels()
    params = EditScheduledEventParams(
        event="Game Night",
        name="Game Night Renamed",
        description="Updated",
        start_time="2026-05-02T18:00:00+00:00",
        end_time="2026-05-02T20:00:00+00:00",
        status="active",
    )
    result = await edit_scheduled_event(params, guild)
    assert "updated" in result.lower()
    edit = guild.scheduled_events[0].edit
    edit.assert_called_once()
    kwargs = edit.call_args.kwargs
    assert isinstance(kwargs["start_time"], datetime)
    assert kwargs["status"] == discord.EventStatus.active


@pytest.mark.asyncio
async def test_edit_scheduled_event_unknown_raises():
    guild = _guild_with_channels()
    params = EditScheduledEventParams(event="ghost")
    with pytest.raises(ValueError, match="Scheduled event not found"):
        await edit_scheduled_event(params, guild)


@pytest.mark.asyncio
async def test_delete_scheduled_event():
    guild = _guild_with_channels()
    await delete_scheduled_event(DeleteScheduledEventParams(event="Game Night"), guild)
    guild.scheduled_events[0].delete.assert_called_once()


@pytest.mark.asyncio
async def test_delete_scheduled_event_unknown_raises():
    guild = _guild_with_channels()
    with pytest.raises(ValueError, match="Scheduled event not found"):
        await delete_scheduled_event(DeleteScheduledEventParams(event="ghost"), guild)
