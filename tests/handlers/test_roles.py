"""Coverage for role handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from architect.executor.handlers.roles import (
    assign_role,
    delete_role,
    edit_role,
    remove_role,
)
from architect.models.params.roles import (
    AssignRoleParams,
    DeleteRoleParams,
    EditRoleParams,
    RemoveRoleParams,
)


def _make_guild() -> MagicMock:
    guild = MagicMock(spec=discord.Guild)
    role = MagicMock()
    role.name = "Mod"
    role.id = 100
    role.edit = AsyncMock()
    role.delete = AsyncMock()
    everyone = MagicMock()
    everyone.name = "@everyone"
    guild.roles = [role, everyone]
    guild.default_role = everyone
    guild.get_role = MagicMock(return_value=None)

    member = MagicMock()
    member.id = 1
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()
    guild.get_member = MagicMock(return_value=member)
    return guild


@pytest.mark.asyncio
async def test_edit_role_full_payload():
    guild = _make_guild()
    params = EditRoleParams(
        role="Mod", name="Senior Mod", color="#ff0000", hoist=True, mentionable=True
    )
    result = await edit_role(params, guild)
    assert "@Mod" in result or "Senior Mod" in result
    edit = guild.roles[0].edit
    edit.assert_called_once()
    kwargs = edit.call_args.kwargs
    assert kwargs["name"] == "Senior Mod"
    assert kwargs["hoist"] is True


@pytest.mark.asyncio
async def test_delete_role_passes_reason():
    guild = _make_guild()
    await delete_role(DeleteRoleParams(role="Mod", reason="cleanup"), guild)
    guild.roles[0].delete.assert_called_once_with(reason="cleanup")


@pytest.mark.asyncio
async def test_assign_role_unknown_user_raises():
    guild = _make_guild()
    guild.get_member = MagicMock(return_value=None)
    with pytest.raises(ValueError, match="Member not found"):
        await assign_role(AssignRoleParams(user="999", role="Mod"), guild)


@pytest.mark.asyncio
async def test_remove_role_unknown_user_raises():
    guild = _make_guild()
    guild.get_member = MagicMock(return_value=None)
    with pytest.raises(ValueError, match="Member not found"):
        await remove_role(RemoveRoleParams(user="999", role="Mod"), guild)


@pytest.mark.asyncio
async def test_assign_and_remove_role_call_member_methods():
    guild = _make_guild()
    member = guild.get_member()
    await assign_role(AssignRoleParams(user="<@1>", role="Mod"), guild)
    member.add_roles.assert_called_once()
    await remove_role(RemoveRoleParams(user="<@1>", role="Mod"), guild)
    member.remove_roles.assert_called_once()
