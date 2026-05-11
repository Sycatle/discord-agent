"""Granular permission-override handler (`set_channel_permission_overrides`).

Supports both role and member targets, with explicit allow + deny lists in
a single call. Complements the coarser `set_channel_permissions` (roles
only) when fine-grained control is needed.
"""

from __future__ import annotations

import discord

from architect.executor._resolve import parse_member, resolve_channel, resolve_role
from architect.models.params.permissions import SetChannelPermissionOverridesParams


def _build_overwrite(
    allow: list[str], deny: list[str]
) -> discord.PermissionOverwrite:
    overwrite = discord.PermissionOverwrite()
    for perm in allow:
        if not hasattr(discord.Permissions, perm):
            raise ValueError(f"Unknown permission flag: {perm!r}")
        setattr(overwrite, perm, True)
    for perm in deny:
        if not hasattr(discord.Permissions, perm):
            raise ValueError(f"Unknown permission flag: {perm!r}")
        setattr(overwrite, perm, False)
    return overwrite


async def set_channel_permission_overrides(
    params: SetChannelPermissionOverridesParams, guild: discord.Guild
) -> str:
    channel = resolve_channel(guild, params.channel)
    if channel is None:
        raise ValueError(f"Channel not found: {params.channel!r}")
    target: discord.Role | discord.Member
    if params.target_type == "role":
        target = resolve_role(guild, params.target)
    else:
        member = parse_member(guild, params.target)
        if member is None:
            raise ValueError(f"Member not found: {params.target!r}")
        target = member
    overwrite = _build_overwrite(params.allow, params.deny)
    await channel.set_permissions(target, overwrite=overwrite, reason=params.reason)
    return (
        f"Overrides set on #{channel.name} for {params.target_type} `{params.target}`: "
        f"+{len(params.allow)} / -{len(params.deny)}"
    )
