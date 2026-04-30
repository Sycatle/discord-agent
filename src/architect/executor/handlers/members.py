"""Member-domain handler."""

from __future__ import annotations

from datetime import datetime

import discord

from architect.executor._resolve import parse_member, resolve_channel
from architect.models.params.members import EditMemberParams


async def edit_member(params: EditMemberParams, guild: discord.Guild) -> str:
    member = parse_member(guild, params.user)
    if member is None:
        raise ValueError(f"Member not found: {params.user!r}")

    fields = params.model_fields_set
    kwargs: dict = {}
    if "nick" in fields:
        kwargs["nick"] = params.nick  # None resets the nickname
    if params.mute is not None:
        kwargs["mute"] = params.mute
    if params.deaf is not None:
        kwargs["deafen"] = params.deaf
    if "timeout_until" in fields:
        kwargs["communication_disabled_until"] = (
            datetime.fromisoformat(params.timeout_until) if params.timeout_until else None
        )
    if params.move_to_channel is not None:
        ch = resolve_channel(guild, params.move_to_channel)
        if ch is None:
            raise ValueError(f"Voice channel not found: {params.move_to_channel!r}")
        kwargs["voice_channel"] = ch
    await member.edit(**kwargs)
    return f"Member {params.user} updated"
