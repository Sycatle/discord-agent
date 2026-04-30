"""Coverage for read-only handler edge cases (empty results, missing data)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from architect.executor.handlers.readonly import (
    GetMemberRolesParams,
    NoParams,
    check_bot_permissions,
    get_member_roles,
    list_automod_rules,
    list_invites,
    list_scheduled_events,
    list_webhooks,
)


def _empty_guild() -> MagicMock:
    guild = MagicMock(spec=discord.Guild)
    guild.invites = AsyncMock(return_value=[])
    guild.webhooks = AsyncMock(return_value=[])
    guild.fetch_auto_moderation_rules = AsyncMock(return_value=[])
    guild.scheduled_events = []
    return guild


@pytest.mark.asyncio
async def test_list_invites_empty():
    assert await list_invites(NoParams(), _empty_guild()) == "No active invites."


@pytest.mark.asyncio
async def test_list_webhooks_empty():
    assert await list_webhooks(NoParams(), _empty_guild()) == "No webhooks."


@pytest.mark.asyncio
async def test_list_automod_rules_empty():
    assert await list_automod_rules(NoParams(), _empty_guild()) == "No AutoMod rules."


@pytest.mark.asyncio
async def test_list_scheduled_events_empty():
    assert await list_scheduled_events(NoParams(), _empty_guild()) == "No scheduled events."


@pytest.mark.asyncio
async def test_check_bot_permissions_no_member():
    guild = _empty_guild()
    guild.me = None
    result = await check_bot_permissions(NoParams(), guild)
    assert "membership missing" in result


@pytest.mark.asyncio
async def test_check_bot_permissions_all_granted():
    guild = _empty_guild()
    perms = type("P", (), {})()
    # Set every required permission to True
    for name in [
        "manage_channels",
        "create_instant_invite",
        "manage_webhooks",
        "manage_roles",
        "moderate_members",
        "manage_events",
        "manage_guild",
    ]:
        setattr(perms, name, True)
    me = MagicMock()
    me.guild_permissions = perms
    guild.me = me
    result = await check_bot_permissions(NoParams(), guild)
    assert "All required permissions are present" in result


@pytest.mark.asyncio
async def test_get_member_roles_unknown_user_raises():
    guild = MagicMock(spec=discord.Guild)
    guild.get_member = MagicMock(return_value=None)
    with pytest.raises(ValueError, match="Member not found"):
        await get_member_roles(GetMemberRolesParams(user="123"), guild)


@pytest.mark.asyncio
async def test_get_member_roles_filters_everyone():
    guild = MagicMock(spec=discord.Guild)
    everyone = MagicMock()
    everyone.name = "@everyone"
    role = MagicMock()
    role.name = "Admin"
    member = MagicMock()
    member.roles = [everyone, role]
    guild.get_member = MagicMock(return_value=member)
    result = await get_member_roles(GetMemberRolesParams(user="123"), guild)
    assert "@everyone" not in result
    assert "Admin" in result
