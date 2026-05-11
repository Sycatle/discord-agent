"""Coverage for moderation handlers (ban / kick / unban / bulk-timeout)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from architect.executor.handlers.moderation import (
    ban_member,
    bulk_timeout_members,
    kick_member,
    unban_member,
)
from architect.models.params.moderation import (
    BanMemberParams,
    BulkTimeoutMembersParams,
    KickMemberParams,
    UnbanMemberParams,
)


def _make_guild_with_member() -> tuple[MagicMock, MagicMock]:
    guild = MagicMock(spec=discord.Guild)
    guild.ban = AsyncMock()
    guild.kick = AsyncMock()
    guild.unban = AsyncMock()
    member = MagicMock()
    member.id = 42
    member.display_name = "Alice"
    member.timeout = AsyncMock()
    guild.get_member = MagicMock(return_value=member)
    return guild, member


@pytest.mark.asyncio
async def test_ban_member():
    guild, member = _make_guild_with_member()
    result = await ban_member(
        BanMemberParams(member="42", delete_message_days=1, reason="spam"),
        guild,
    )
    guild.ban.assert_awaited_once_with(member, reason="spam", delete_message_days=1)
    assert "Alice" in result


@pytest.mark.asyncio
async def test_ban_member_not_found():
    guild = MagicMock(spec=discord.Guild)
    guild.get_member = MagicMock(return_value=None)
    with pytest.raises(ValueError, match="not found"):
        await ban_member(BanMemberParams(member="999"), guild)


@pytest.mark.asyncio
async def test_kick_member():
    guild, member = _make_guild_with_member()
    await kick_member(KickMemberParams(member="42", reason="rules"), guild)
    guild.kick.assert_awaited_once_with(member, reason="rules")


@pytest.mark.asyncio
async def test_unban_member_by_id():
    guild = MagicMock(spec=discord.Guild)
    guild.unban = AsyncMock()
    await unban_member(UnbanMemberParams(user_id="123", reason="appeal"), guild)
    guild.unban.assert_awaited_once()
    args, kwargs = guild.unban.call_args
    assert args[0].id == 123
    assert kwargs["reason"] == "appeal"


@pytest.mark.asyncio
async def test_unban_member_invalid_id():
    guild = MagicMock(spec=discord.Guild)
    with pytest.raises(ValueError, match="numeric user_id"):
        await unban_member(UnbanMemberParams(user_id="not-a-number"), guild)


@pytest.mark.asyncio
async def test_bulk_timeout_members_all_succeed():
    guild = MagicMock(spec=discord.Guild)
    member_a = MagicMock()
    member_a.display_name = "Alice"
    member_a.timeout = AsyncMock()
    member_b = MagicMock()
    member_b.display_name = "Bob"
    member_b.timeout = AsyncMock()
    guild.get_member = MagicMock(side_effect=[member_a, member_b])
    result = await bulk_timeout_members(
        BulkTimeoutMembersParams(members=["1", "2"], duration_minutes=10),
        guild,
    )
    member_a.timeout.assert_awaited_once()
    member_b.timeout.assert_awaited_once()
    assert "Timed out 2" in result


@pytest.mark.asyncio
async def test_bulk_timeout_members_partial_failure():
    guild = MagicMock(spec=discord.Guild)
    member_a = MagicMock()
    member_a.display_name = "Alice"
    member_a.timeout = AsyncMock()
    guild.get_member = MagicMock(side_effect=[member_a, None])
    result = await bulk_timeout_members(
        BulkTimeoutMembersParams(members=["1", "2"], duration_minutes=5),
        guild,
    )
    assert "Timed out 1" in result
    assert "Failed:" in result
