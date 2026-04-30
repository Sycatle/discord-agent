"""Server-settings and welcome-screen handlers."""

from __future__ import annotations

import discord

from architect.executor._resolve import resolve_channel
from architect.models.params.server import (
    EditServerParams,
    EditWelcomeScreenParams,
)

_NOTIF_MAP = {
    "all_messages": discord.NotificationLevel.all_messages,
    "only_mentions": discord.NotificationLevel.only_mentions,
}

_FILTER_MAP = {
    "disabled": discord.ContentFilter.disabled,
    "members_without_roles": discord.ContentFilter.no_role,
    "all_members": discord.ContentFilter.all_members,
}

_SERVER_CHANNEL_FIELDS = (
    "system_channel",
    "rules_channel",
    "public_updates_channel",
    "safety_alerts_channel",
)


async def edit_server(params: EditServerParams, guild: discord.Guild) -> str:
    fields = params.model_fields_set
    kwargs: dict = {}
    if params.name is not None:
        kwargs["name"] = params.name
    if params.verification_level is not None:
        kwargs["verification_level"] = discord.VerificationLevel[params.verification_level]
    if params.default_message_notifications is not None:
        kwargs["default_notifications"] = _NOTIF_MAP[params.default_message_notifications]
    if params.explicit_content_filter is not None:
        kwargs["explicit_content_filter"] = _FILTER_MAP[params.explicit_content_filter]
    if "afk_channel" in fields:
        kwargs["afk_channel"] = (
            resolve_channel(guild, params.afk_channel) if params.afk_channel else None
        )
    if params.afk_timeout is not None:
        kwargs["afk_timeout"] = params.afk_timeout
    for field in _SERVER_CHANNEL_FIELDS:
        if field in fields:
            raw = getattr(params, field)
            kwargs[field] = resolve_channel(guild, raw) if raw else None
    if params.description is not None:
        kwargs["description"] = params.description
    if params.preferred_locale is not None:
        # Locale values are BCP-47 tags (e.g. "fr", "en-US")
        kwargs["preferred_locale"] = discord.Locale(params.preferred_locale.replace("_", "-"))
    if params.premium_progress_bar_enabled is not None:
        kwargs["premium_progress_bar_enabled"] = params.premium_progress_bar_enabled
    if params.community is not None:
        if params.community is True:
            rules_ch = kwargs.get("rules_channel") or params.rules_channel
            updates_ch = kwargs.get("public_updates_channel") or params.public_updates_channel
            if not rules_ch or not updates_ch:
                raise ValueError("community mode requires rules_channel and public_updates_channel")
        kwargs["community"] = params.community
    await guild.edit(**kwargs)
    return "Server settings updated"


async def edit_welcome_screen(params: EditWelcomeScreenParams, guild: discord.Guild) -> str:
    kwargs: dict = {}
    if params.enabled is not None:
        kwargs["enabled"] = params.enabled
    if params.description is not None:
        kwargs["description"] = params.description
    if params.welcome_channels:
        channels: list[discord.WelcomeChannel] = []
        for entry in params.welcome_channels:
            ch = resolve_channel(guild, entry.channel)
            if ch is None:
                raise ValueError(f"Welcome channel not found: {entry.channel!r}")
            emoji = discord.PartialEmoji.from_str(entry.emoji) if entry.emoji else None
            channels.append(
                discord.WelcomeChannel(channel=ch, description=entry.description, emoji=emoji)
            )
        kwargs["welcome_channels"] = channels
    await guild.edit_welcome_screen(**kwargs)
    return "Welcome screen updated"
