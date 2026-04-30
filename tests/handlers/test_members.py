"""Coverage for the edit_member handler error paths."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from architect.executor.handlers.members import edit_member
from architect.models.params.members import EditMemberParams


def _guild_with_member() -> MagicMock:
    guild = MagicMock(spec=discord.Guild)
    member = MagicMock()
    member.id = 1
    member.edit = AsyncMock()
    guild.get_member = MagicMock(return_value=member)
    voice = MagicMock()
    voice.name = "voice-room"
    voice.id = 99
    guild.channels = [voice]
    guild.get_channel = MagicMock(return_value=None)
    return guild


@pytest.mark.asyncio
async def test_edit_member_unknown_user_raises():
    guild = _guild_with_member()
    guild.get_member = MagicMock(return_value=None)
    with pytest.raises(ValueError, match="Member not found"):
        await edit_member(EditMemberParams(user="<@999>"), guild)


@pytest.mark.asyncio
async def test_edit_member_unknown_voice_channel_raises():
    guild = _guild_with_member()
    with pytest.raises(ValueError, match="Voice channel not found"):
        await edit_member(EditMemberParams(user="<@1>", move_to_channel="ghost"), guild)


@pytest.mark.asyncio
async def test_edit_member_full_payload():
    guild = _guild_with_member()
    params = EditMemberParams(
        user="<@1>",
        nick="Bob",
        mute=True,
        deaf=True,
        timeout_until="2026-12-31T23:59:59+00:00",
        move_to_channel="voice-room",
    )
    await edit_member(params, guild)
    member = guild.get_member()
    member.edit.assert_called_once()
    kwargs = member.edit.call_args.kwargs
    assert kwargs["nick"] == "Bob"
    assert kwargs["mute"] is True
    assert kwargs["deafen"] is True
    assert kwargs["communication_disabled_until"] is not None


@pytest.mark.asyncio
async def test_edit_member_clears_timeout():
    guild = _guild_with_member()
    params = EditMemberParams(user="<@1>", timeout_until=None)
    await edit_member(params, guild)
    kwargs = guild.get_member().edit.call_args.kwargs
    assert kwargs["communication_disabled_until"] is None


@pytest.mark.asyncio
async def test_edit_member_resets_nick_to_none():
    guild = _guild_with_member()
    params = EditMemberParams(user="<@1>", nick=None)
    await edit_member(params, guild)
    kwargs = guild.get_member().edit.call_args.kwargs
    assert kwargs["nick"] is None
