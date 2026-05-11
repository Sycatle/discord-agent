"""Thread-domain handlers (create / archive / lock / unarchive)."""

from __future__ import annotations

import contextlib

import discord

from architect.executor._resolve import resolve_channel
from architect.models.params.threads import (
    ArchiveThreadParams,
    CreateThreadParams,
    LockThreadParams,
    UnarchiveThreadParams,
)


def _resolve_thread(guild: discord.Guild, name_or_id: str) -> discord.Thread | None:
    """Find a thread by ID or name across active threads."""
    with contextlib.suppress(ValueError, TypeError):
        thread_id = int(name_or_id)
        for t in guild.threads:
            if t.id == thread_id:
                return t
    return next((t for t in guild.threads if t.name == name_or_id), None)


async def create_thread(params: CreateThreadParams, guild: discord.Guild) -> str:
    parent = resolve_channel(guild, params.parent_channel)
    if parent is None:
        raise ValueError(f"Parent channel not found: {params.parent_channel!r}")
    if not isinstance(
        parent, discord.TextChannel | discord.ForumChannel
    ):
        raise ValueError(
            f"Parent channel `{params.parent_channel}` is not a text or forum channel"
        )
    kwargs: dict = {"name": params.name}
    if isinstance(parent, discord.TextChannel):
        kwargs["type"] = (
            discord.ChannelType.private_thread
            if params.type == "private"
            else discord.ChannelType.public_thread
        )
    if params.auto_archive_minutes is not None:
        kwargs["auto_archive_duration"] = params.auto_archive_minutes
    if params.reason is not None:
        kwargs["reason"] = params.reason
    if isinstance(parent, discord.ForumChannel):
        # Forum threads require an initial message — auto-generate one.
        kwargs["content"] = f"Thread `{params.name}` created."
    await parent.create_thread(**kwargs)
    return f"Thread created: {params.name} → #{parent.name}"


async def archive_thread(params: ArchiveThreadParams, guild: discord.Guild) -> str:
    thread = _resolve_thread(guild, params.thread)
    if thread is None:
        raise ValueError(f"Thread not found: {params.thread!r}")
    await thread.edit(archived=True, reason=params.reason)
    return f"Thread archived: {thread.name}"


async def unarchive_thread(
    params: UnarchiveThreadParams, guild: discord.Guild
) -> str:
    thread = _resolve_thread(guild, params.thread)
    if thread is None:
        raise ValueError(f"Thread not found: {params.thread!r}")
    await thread.edit(archived=False, reason=params.reason)
    return f"Thread unarchived: {thread.name}"


async def lock_thread(params: LockThreadParams, guild: discord.Guild) -> str:
    thread = _resolve_thread(guild, params.thread)
    if thread is None:
        raise ValueError(f"Thread not found: {params.thread!r}")
    await thread.edit(locked=True, reason=params.reason)
    return f"Thread locked: {thread.name}"
