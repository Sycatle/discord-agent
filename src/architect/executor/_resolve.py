"""Shared lookup helpers used by handlers (channels, roles, webhooks, etc.).

Each ``resolve_*`` function accepts the user-facing string the LLM produced
(typically a Discord name or numeric ID) and returns the matching object —
or ``None`` if no match was found. ``parse_color`` and ``parse_member`` map
loosely typed inputs onto their Discord SDK counterparts.
"""

from __future__ import annotations

import contextlib
import re

import discord


def resolve_channel(guild: discord.Guild, name_or_id: str) -> discord.abc.GuildChannel | None:
    with contextlib.suppress(ValueError, TypeError):
        ch = guild.get_channel(int(name_or_id))
        if ch is not None:
            return ch
    return discord.utils.get(guild.channels, name=name_or_id)


def resolve_category(
    guild: discord.Guild, category_name: str | None
) -> discord.CategoryChannel | None:
    if category_name is None:
        return None
    return discord.utils.get(guild.categories, name=category_name)


def resolve_role(guild: discord.Guild, name_or_id: str) -> discord.Role:
    role: discord.Role | None = None
    with contextlib.suppress(ValueError, TypeError):
        role = guild.get_role(int(name_or_id))
    if role is None:
        role = discord.utils.get(guild.roles, name=name_or_id)
    if role is None:
        raise ValueError(f"Role not found: {name_or_id!r}")
    if role == guild.default_role:
        raise ValueError("Cannot target @everyone")
    return role


def parse_member(guild: discord.Guild, user_str: str) -> discord.Member | None:
    m = re.match(r"<@!?(\d+)>", user_str.strip())
    user_id = int(m.group(1)) if m else int(user_str.strip())
    return guild.get_member(user_id)


async def resolve_webhook(guild: discord.Guild, name_or_id: str) -> discord.Webhook | None:
    webhooks = await guild.webhooks()
    try:
        wh_id = int(name_or_id)
        return next((w for w in webhooks if w.id == wh_id), None)
    except (ValueError, TypeError):
        return next((w for w in webhooks if w.name == name_or_id), None)


def resolve_scheduled_event(guild: discord.Guild, name_or_id: str) -> discord.ScheduledEvent | None:
    try:
        evt_id = int(name_or_id)
        return next((e for e in guild.scheduled_events if e.id == evt_id), None)
    except (ValueError, TypeError):
        return next((e for e in guild.scheduled_events if e.name == name_or_id), None)


def parse_color(color_val: str | int | None) -> discord.Color:
    if color_val is None:
        return discord.Color.default()
    if isinstance(color_val, int):
        return discord.Color(color_val)
    if isinstance(color_val, str):
        return discord.Color(int(color_val.lstrip("#"), 16))
    return discord.Color.default()
