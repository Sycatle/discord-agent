"""Read-only handlers (no mutations).

These are dispatched without permission checks (they don't mutate state)
and accept either a typed Pydantic model or no params at all. They share
the same signature as mutation handlers so the registry stays uniform.
"""

from __future__ import annotations

import discord
from pydantic import BaseModel, ConfigDict, Field

from architect.executor._resolve import parse_member
from architect.executor.permissions import REQUIRED_PERMISSIONS


class NoParams(BaseModel):
    """Marker model for read-only tools that take no parameters."""

    model_config = ConfigDict(extra="forbid")


class GetMemberRolesParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: str = Field(description="@mention or numeric user_id")


async def list_channels(_: NoParams, guild: discord.Guild) -> str:
    categories = ", ".join(c.name for c in guild.categories)
    text_channels = ", ".join(f"#{c.name}" for c in guild.text_channels)
    voice_channels = ", ".join(c.name for c in guild.voice_channels)
    return (
        f"Categories: {categories}\n"
        f"Text channels: {text_channels}\n"
        f"Voice channels: {voice_channels}"
    )


async def list_roles(_: NoParams, guild: discord.Guild) -> str:
    roles = ", ".join(r.name for r in guild.roles if r.name != "@everyone")
    return f"Roles: {roles}"


async def get_member_roles(params: GetMemberRolesParams, guild: discord.Guild) -> str:
    member = parse_member(guild, params.user)
    if member is None:
        raise ValueError(f"Member not found: {params.user!r}")
    roles = [r.name for r in member.roles if r.name != "@everyone"]
    return f"Roles of {params.user}: {', '.join(roles) or 'none'}"


async def get_server_info(_: NoParams, guild: discord.Guild) -> str:
    return (
        f"Server: {guild.name}\n"
        f"Members: {guild.member_count}\n"
        f"Verification: {guild.verification_level}\n"
        f"Content filter: {guild.explicit_content_filter}\n"
        f"Notifications: {guild.default_notifications}\n"
        f"Boost: tier {guild.premium_tier} ({guild.premium_subscription_count} boosts)\n"
        f"Locale: {guild.preferred_locale}"
    )


async def list_invites(_: NoParams, guild: discord.Guild) -> str:
    invites = await guild.invites()
    if not invites:
        return "No active invites."
    lines = [
        f"- {i.code} → #{i.channel.name if i.channel else '?'} ({i.uses}/{i.max_uses or '∞'} uses)"
        for i in invites
    ]
    return "Invites:\n" + "\n".join(lines)


async def list_webhooks(_: NoParams, guild: discord.Guild) -> str:
    webhooks = await guild.webhooks()
    if not webhooks:
        return "No webhooks."
    lines = [f"- {w.name} → #{w.channel.name if w.channel else '?'}" for w in webhooks]
    return "Webhooks:\n" + "\n".join(lines)


async def list_scheduled_events(_: NoParams, guild: discord.Guild) -> str:
    events = guild.scheduled_events
    if not events:
        return "No scheduled events."
    lines = [f"- {e.name} ({e.entity_type}) — {e.start_time}" for e in events]
    return "Events:\n" + "\n".join(lines)


async def list_automod_rules(_: NoParams, guild: discord.Guild) -> str:
    rules = await guild.fetch_auto_moderation_rules()
    if not rules:
        return "No AutoMod rules."
    lines = [f"- {r.name} ({'enabled' if r.enabled else 'disabled'})" for r in rules]
    return "AutoMod rules:\n" + "\n".join(lines)


async def check_bot_permissions(_: NoParams, guild: discord.Guild) -> str:
    me = guild.me
    if me is None:
        return "Cannot read bot permissions (membership missing)."
    perms = me.guild_permissions
    required_perms = sorted(set(REQUIRED_PERMISSIONS.values()))
    granted = [p for p in required_perms if getattr(perms, p, False)]
    missing = [p for p in required_perms if not getattr(perms, p, False)]
    lines = [f"Granted permissions: {', '.join(granted) or 'none'}"]
    if missing:
        lines.append(f"Missing permissions: {', '.join(missing)}")
    else:
        lines.append("All required permissions are present.")
    return "\n".join(lines)


__all__ = [
    "GetMemberRolesParams",
    "NoParams",
    "check_bot_permissions",
    "get_member_roles",
    "get_server_info",
    "list_automod_rules",
    "list_channels",
    "list_invites",
    "list_roles",
    "list_scheduled_events",
    "list_webhooks",
]
