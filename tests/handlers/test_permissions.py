"""Coverage for the granular permission-override handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from architect.executor.handlers.permissions import (
    set_channel_permission_overrides,
)
from architect.models.params.permissions import SetChannelPermissionOverridesParams


def _make_guild() -> tuple[MagicMock, MagicMock, MagicMock]:
    guild = MagicMock(spec=discord.Guild)
    role = MagicMock()
    role.name = "Mod"
    role.id = 100
    everyone = MagicMock()
    everyone.name = "@everyone"
    guild.roles = [role, everyone]
    guild.default_role = everyone
    guild.get_role = MagicMock(return_value=None)

    channel = MagicMock()
    channel.name = "general"
    channel.id = 10
    channel.set_permissions = AsyncMock()
    guild.channels = [channel]
    guild.get_channel = MagicMock(return_value=None)
    return guild, channel, role


@pytest.mark.asyncio
async def test_set_overrides_for_role():
    guild, channel, _role = _make_guild()
    result = await set_channel_permission_overrides(
        SetChannelPermissionOverridesParams(
            channel="general",
            target_type="role",
            target="Mod",
            allow=["manage_messages"],
            deny=["send_messages"],
        ),
        guild,
    )
    channel.set_permissions.assert_awaited_once()
    assert "+1 / -1" in result


@pytest.mark.asyncio
async def test_set_overrides_unknown_perm_flag_raises():
    guild, _channel, _role = _make_guild()
    with pytest.raises(ValueError, match="Unknown permission flag"):
        await set_channel_permission_overrides(
            SetChannelPermissionOverridesParams(
                channel="general",
                target_type="role",
                target="Mod",
                allow=["definitely_not_a_perm"],
            ),
            guild,
        )


@pytest.mark.asyncio
async def test_set_overrides_unknown_channel():
    guild = MagicMock(spec=discord.Guild)
    guild.channels = []
    guild.get_channel = MagicMock(return_value=None)
    with pytest.raises(ValueError, match="Channel not found"):
        await set_channel_permission_overrides(
            SetChannelPermissionOverridesParams(
                channel="ghost",
                target_type="role",
                target="Mod",
                allow=["manage_messages"],
            ),
            guild,
        )


@pytest.mark.asyncio
async def test_set_overrides_for_member():
    guild, channel, _role = _make_guild()
    member = MagicMock()
    member.id = 99
    guild.get_member = MagicMock(return_value=member)
    result = await set_channel_permission_overrides(
        SetChannelPermissionOverridesParams(
            channel="general",
            target_type="member",
            target="99",
            allow=["view_channel"],
        ),
        guild,
    )
    args, kwargs = channel.set_permissions.call_args
    assert args[0] is member
    assert "+1 / -0" in result
