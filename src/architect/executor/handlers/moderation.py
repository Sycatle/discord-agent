"""Moderation handlers (ban / kick / unban / bulk-timeout)."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta

import discord

from architect.executor._resolve import parse_member
from architect.models.params.moderation import (
    BanMemberParams,
    BulkTimeoutMembersParams,
    KickMemberParams,
    UnbanMemberParams,
)


async def ban_member(params: BanMemberParams, guild: discord.Guild) -> str:
    member = parse_member(guild, params.member)
    if member is None:
        raise ValueError(f"Member not found: {params.member!r}")
    await guild.ban(
        member,
        reason=params.reason,
        delete_message_days=params.delete_message_days,
    )
    return f"Banned: {member.display_name} ({member.id})"


async def kick_member(params: KickMemberParams, guild: discord.Guild) -> str:
    member = parse_member(guild, params.member)
    if member is None:
        raise ValueError(f"Member not found: {params.member!r}")
    await guild.kick(member, reason=params.reason)
    return f"Kicked: {member.display_name} ({member.id})"


async def unban_member(params: UnbanMemberParams, guild: discord.Guild) -> str:
    try:
        user_id = int(params.user_id)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"unban_member expects a numeric user_id, got {params.user_id!r}"
        ) from exc
    user = discord.Object(id=user_id)
    await guild.unban(user, reason=params.reason)
    return f"Unbanned user_id: {user_id}"


async def bulk_timeout_members(
    params: BulkTimeoutMembersParams, guild: discord.Guild
) -> str:
    """Timeout up to 50 members sequentially with a small backoff."""
    until = datetime.now(UTC) + timedelta(minutes=params.duration_minutes)
    succeeded: list[str] = []
    failed: list[str] = []
    for target in params.members:
        try:
            member = parse_member(guild, target)
        except ValueError:
            failed.append(f"{target} (invalid id)")
            continue
        if member is None:
            failed.append(f"{target} (not found)")
            continue
        try:
            await member.timeout(until, reason=params.reason)
            succeeded.append(member.display_name)
        except discord.HTTPException as e:
            failed.append(f"{target} ({e.status})")
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.sleep(0.4)  # gentle pacing for Discord's per-route bucket
    parts = [f"Timed out {len(succeeded)} member(s) for {params.duration_minutes}m."]
    if failed:
        parts.append(f"Failed: {', '.join(failed)}")
    return " ".join(parts)
