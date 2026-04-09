import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from architect.executor.executor import Executor


def _make_guild():
    guild = MagicMock()

    cat = MagicMock()
    cat.name = "Gaming"

    ch_text = MagicMock()
    ch_text.name = "general"

    ch_voice = MagicMock()
    ch_voice.name = "Vocal"

    role_admin = MagicMock()
    role_admin.name = "Admin"

    role_everyone = MagicMock()
    role_everyone.name = "@everyone"

    guild.categories = [cat]
    guild.text_channels = [ch_text]
    guild.voice_channels = [ch_voice]
    guild.channels = [ch_text, ch_voice]
    guild.roles = [role_admin, role_everyone]

    created_category = MagicMock()
    created_category.name = "NewCat"
    guild.create_category = AsyncMock(return_value=created_category)

    created_text = MagicMock()
    created_text.name = "new-channel"
    guild.create_text_channel = AsyncMock(return_value=created_text)

    created_voice = MagicMock()
    created_voice.name = "New Voice"
    guild.create_voice_channel = AsyncMock(return_value=created_voice)

    created_role = MagicMock()
    created_role.name = "Moderator"
    guild.create_role = AsyncMock(return_value=created_role)

    ch_text.set_permissions = AsyncMock()

    return guild


@pytest.mark.asyncio
async def test_create_category():
    guild = _make_guild()
    executor = Executor()
    result = await executor.execute("create_category", {"name": "NewCat"}, guild)
    guild.create_category.assert_called_once_with(name="NewCat")
    assert result == "Category created: NewCat"


@pytest.mark.asyncio
async def test_create_text_channel():
    guild = _make_guild()
    executor = Executor()
    result = await executor.execute("create_text_channel", {"name": "new-channel"}, guild)
    guild.create_text_channel.assert_called_once_with(name="new-channel", category=None)
    assert result == "Text channel created: #new-channel"


@pytest.mark.asyncio
async def test_create_text_channel_with_category():
    guild = _make_guild()
    executor = Executor()

    import discord
    with patch.object(discord.utils, "get", return_value=guild.categories[0]):
        result = await executor.execute(
            "create_text_channel",
            {"name": "news", "category": "Gaming"},
            guild,
        )
    guild.create_text_channel.assert_called_once_with(
        name="news", category=guild.categories[0]
    )
    assert result == "Text channel created: #news"


@pytest.mark.asyncio
async def test_create_voice_channel():
    guild = _make_guild()
    executor = Executor()
    result = await executor.execute("create_voice_channel", {"name": "New Voice"}, guild)
    guild.create_voice_channel.assert_called_once_with(name="New Voice", category=None)
    assert result == "Voice channel created: New Voice"


@pytest.mark.asyncio
async def test_create_role_with_hex_color():
    guild = _make_guild()
    executor = Executor()

    import discord
    result = await executor.execute(
        "create_role",
        {"name": "Moderator", "color": "#ff0000", "mentionable": True},
        guild,
    )
    guild.create_role.assert_called_once_with(
        name="Moderator",
        color=discord.Color(0xFF0000),
        mentionable=True,
    )
    assert result == "Role created: @Moderator"


@pytest.mark.asyncio
async def test_create_role_with_int_color():
    guild = _make_guild()
    executor = Executor()

    import discord
    result = await executor.execute(
        "create_role",
        {"name": "Member", "color": 0x00FF00},
        guild,
    )
    guild.create_role.assert_called_once_with(
        name="Member",
        color=discord.Color(0x00FF00),
        mentionable=False,
    )
    assert result == "Role created: @Member"


@pytest.mark.asyncio
async def test_set_channel_permissions():
    guild = _make_guild()
    executor = Executor()

    import discord

    ch_text = guild.text_channels[0]
    role_admin = guild.roles[0]

    with patch.object(discord.utils, "get", side_effect=[ch_text, role_admin]):
        result = await executor.execute(
            "set_channel_permissions",
            {
                "channel": "general",
                "role": "Admin",
                "overwrite": {"read_messages": True, "send_messages": False},
            },
            guild,
        )

    ch_text.set_permissions.assert_called_once()
    assert result == "Permissions set: #general → @Admin"


@pytest.mark.asyncio
async def test_list_channels():
    guild = _make_guild()
    executor = Executor()
    result = await executor.execute("list_channels", {}, guild)
    assert "Categories: Gaming" in result
    assert "Text channels: #general" in result
    assert "Voice channels: Vocal" in result


@pytest.mark.asyncio
async def test_list_roles_excludes_everyone():
    guild = _make_guild()
    executor = Executor()
    result = await executor.execute("list_roles", {}, guild)
    assert "Admin" in result
    assert "@everyone" not in result
    assert result.startswith("Roles:")


@pytest.mark.asyncio
async def test_unknown_tool_raises():
    guild = _make_guild()
    executor = Executor()
    with pytest.raises(NotImplementedError, match="No handler for tool"):
        await executor.execute("delete_everything", {}, guild)
