"""Scheduled-event handlers."""

from __future__ import annotations

from datetime import datetime

import discord

from architect.executor._resolve import resolve_channel, resolve_scheduled_event
from architect.models.params.events import (
    CreateScheduledEventParams,
    DeleteScheduledEventParams,
    EditScheduledEventParams,
)

_ENTITY_TYPE_MAP = {
    "voice": discord.EntityType.voice,
    "stage": discord.EntityType.stage_instance,
    "external": discord.EntityType.external,
}

_STATUS_MAP = {
    "active": discord.EventStatus.active,
    "completed": discord.EventStatus.completed,
    "canceled": discord.EventStatus.canceled,
}


async def create_scheduled_event(params: CreateScheduledEventParams, guild: discord.Guild) -> str:
    entity_type = _ENTITY_TYPE_MAP[params.entity_type]
    start = datetime.fromisoformat(params.start_time)
    kwargs: dict = {
        "name": params.name,
        "start_time": start,
        "privacy_level": discord.PrivacyLevel.guild_only,
        "entity_type": entity_type,
    }
    if params.end_time:
        kwargs["end_time"] = datetime.fromisoformat(params.end_time)
    if params.description:
        kwargs["description"] = params.description
    if entity_type == discord.EntityType.external:
        if params.location is None:
            raise ValueError("external scheduled events require a location")
        kwargs["location"] = params.location
    else:
        if params.channel is None:
            raise ValueError("voice/stage scheduled events require a channel")
        ch = resolve_channel(guild, params.channel)
        if ch is None:
            raise ValueError(f"Channel not found: {params.channel!r}")
        kwargs["channel"] = ch
    event = await guild.create_scheduled_event(**kwargs)
    return f"Scheduled event created: {event.name}"


async def edit_scheduled_event(params: EditScheduledEventParams, guild: discord.Guild) -> str:
    event = resolve_scheduled_event(guild, params.event)
    if event is None:
        raise ValueError(f"Scheduled event not found: {params.event!r}")
    kwargs: dict = {}
    if params.name is not None:
        kwargs["name"] = params.name
    if params.description is not None:
        kwargs["description"] = params.description
    if params.start_time is not None:
        kwargs["start_time"] = datetime.fromisoformat(params.start_time)
    if params.end_time is not None:
        kwargs["end_time"] = datetime.fromisoformat(params.end_time)
    if params.status is not None:
        kwargs["status"] = _STATUS_MAP[params.status]
    await event.edit(**kwargs)
    return f"Event updated: {params.event}"


async def delete_scheduled_event(params: DeleteScheduledEventParams, guild: discord.Guild) -> str:
    event = resolve_scheduled_event(guild, params.event)
    if event is None:
        raise ValueError(f"Scheduled event not found: {params.event!r}")
    await event.delete()
    return f"Event deleted: {params.event}"
