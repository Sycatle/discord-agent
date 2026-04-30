"""Coverage for server-settings and welcome-screen handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from architect.executor.handlers.server import edit_server, edit_welcome_screen
from architect.models.params.server import (
    EditServerParams,
    EditWelcomeScreenParams,
    WelcomeChannelEntry,
)


def _guild_with_channels() -> MagicMock:
    guild = MagicMock(spec=discord.Guild)
    afk = MagicMock()
    afk.name = "afk"
    rules = MagicMock()
    rules.name = "rules"
    updates = MagicMock()
    updates.name = "updates"
    system = MagicMock()
    system.name = "system"
    safety = MagicMock()
    safety.name = "safety"
    guild.channels = [afk, rules, updates, system, safety]
    guild.get_channel = MagicMock(return_value=None)
    guild.edit = AsyncMock()
    guild.edit_welcome_screen = AsyncMock()
    return guild


@pytest.mark.asyncio
async def test_edit_server_with_full_payload_calls_guild_edit():
    guild = _guild_with_channels()
    params = EditServerParams(
        name="My Server",
        verification_level="medium",
        default_message_notifications="only_mentions",
        explicit_content_filter="all_members",
        afk_channel="afk",
        afk_timeout=60,
        system_channel="system",
        rules_channel="rules",
        public_updates_channel="updates",
        safety_alerts_channel="safety",
        description="A server",
        preferred_locale="en-US",
        premium_progress_bar_enabled=True,
    )
    result = await edit_server(params, guild)
    assert result == "Server settings updated"
    guild.edit.assert_called_once()
    kwargs = guild.edit.call_args.kwargs
    assert kwargs["name"] == "My Server"
    assert kwargs["verification_level"] == discord.VerificationLevel.medium


@pytest.mark.asyncio
async def test_edit_server_clears_afk_channel_when_set_to_none():
    guild = _guild_with_channels()
    params = EditServerParams(afk_channel=None)
    await edit_server(params, guild)
    guild.edit.assert_called_once()
    kwargs = guild.edit.call_args.kwargs
    assert kwargs["afk_channel"] is None


@pytest.mark.asyncio
async def test_edit_server_locale_normalises_underscore_to_dash():
    """Discord uses BCP-47 (dash) so 'en_US' must be coerced to 'en-US'."""
    guild = _guild_with_channels()
    params = EditServerParams(preferred_locale="en_US")
    await edit_server(params, guild)
    kwargs = guild.edit.call_args.kwargs
    assert kwargs["preferred_locale"] == discord.Locale("en-US")


@pytest.mark.asyncio
async def test_edit_server_community_true_requires_rules_and_updates_channels():
    guild = _guild_with_channels()
    params = EditServerParams(community=True)
    with pytest.raises(ValueError, match="rules_channel and public_updates_channel"):
        await edit_server(params, guild)


@pytest.mark.asyncio
async def test_edit_server_community_true_with_required_channels_succeeds():
    guild = _guild_with_channels()
    params = EditServerParams(
        community=True, rules_channel="rules", public_updates_channel="updates"
    )
    await edit_server(params, guild)
    assert guild.edit.call_args.kwargs["community"] is True


@pytest.mark.asyncio
async def test_edit_server_community_false_skips_channel_check():
    guild = _guild_with_channels()
    params = EditServerParams(community=False)
    await edit_server(params, guild)
    assert guild.edit.call_args.kwargs["community"] is False


# ── Welcome screen ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_welcome_screen_with_channels():
    guild = _guild_with_channels()
    params = EditWelcomeScreenParams(
        enabled=True,
        description="Welcome!",
        welcome_channels=[
            WelcomeChannelEntry(channel="rules", description="Rules", emoji="📜"),
            WelcomeChannelEntry(channel="system", description="System"),
        ],
    )
    result = await edit_welcome_screen(params, guild)
    assert result == "Welcome screen updated"
    guild.edit_welcome_screen.assert_called_once()
    kwargs = guild.edit_welcome_screen.call_args.kwargs
    assert len(kwargs["welcome_channels"]) == 2


@pytest.mark.asyncio
async def test_edit_welcome_screen_unknown_channel_raises():
    guild = _guild_with_channels()
    params = EditWelcomeScreenParams(
        welcome_channels=[WelcomeChannelEntry(channel="ghost", description="?", emoji=None)],
    )
    with pytest.raises(ValueError, match="Welcome channel not found"):
        await edit_welcome_screen(params, guild)


@pytest.mark.asyncio
async def test_edit_welcome_screen_disabled_only():
    guild = _guild_with_channels()
    params = EditWelcomeScreenParams(enabled=False)
    await edit_welcome_screen(params, guild)
    kwargs = guild.edit_welcome_screen.call_args.kwargs
    assert kwargs == {"enabled": False}
