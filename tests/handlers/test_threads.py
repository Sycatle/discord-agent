"""Coverage for thread handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from architect.executor.handlers.threads import (
    archive_thread,
    create_thread,
    lock_thread,
    unarchive_thread,
)
from architect.models.params.threads import (
    ArchiveThreadParams,
    CreateThreadParams,
    LockThreadParams,
    UnarchiveThreadParams,
)


def _make_guild_with_text_channel() -> MagicMock:
    guild = MagicMock(spec=discord.Guild)
    parent = MagicMock(spec=discord.TextChannel)
    parent.name = "help"
    parent.id = 10
    parent.create_thread = AsyncMock()
    guild.text_channels = [parent]
    guild.channels = [parent]
    guild.get_channel = MagicMock(return_value=None)
    return guild


def _make_guild_with_thread() -> tuple[MagicMock, MagicMock]:
    guild = MagicMock(spec=discord.Guild)
    thread = MagicMock(spec=discord.Thread)
    thread.id = 200
    thread.name = "FAQ"
    thread.edit = AsyncMock()
    guild.threads = [thread]
    guild.get_channel = MagicMock(return_value=None)
    return guild, thread


@pytest.mark.asyncio
async def test_create_thread_in_text_channel():
    guild = _make_guild_with_text_channel()
    parent = guild.text_channels[0]

    # discord.utils.get walks guild.channels and matches by name
    result = await create_thread(
        CreateThreadParams(parent_channel="help", name="FAQ", type="public"),
        guild,
    )
    parent.create_thread.assert_awaited_once()
    kwargs = parent.create_thread.await_args.kwargs
    assert kwargs["name"] == "FAQ"
    assert kwargs["type"] == discord.ChannelType.public_thread
    assert "FAQ" in result


@pytest.mark.asyncio
async def test_create_thread_private():
    guild = _make_guild_with_text_channel()
    parent = guild.text_channels[0]
    await create_thread(
        CreateThreadParams(parent_channel="help", name="Secret", type="private"),
        guild,
    )
    kwargs = parent.create_thread.await_args.kwargs
    assert kwargs["type"] == discord.ChannelType.private_thread


@pytest.mark.asyncio
async def test_create_thread_unknown_parent_raises():
    guild = MagicMock(spec=discord.Guild)
    guild.channels = []
    guild.get_channel = MagicMock(return_value=None)
    with pytest.raises(ValueError, match="not found"):
        await create_thread(
            CreateThreadParams(parent_channel="ghost", name="x"), guild
        )


@pytest.mark.asyncio
async def test_create_thread_rejects_voice_parent():
    guild = MagicMock(spec=discord.Guild)
    voice = MagicMock(spec=discord.VoiceChannel)
    voice.name = "lobby"
    guild.channels = [voice]
    guild.get_channel = MagicMock(return_value=None)
    with pytest.raises(ValueError, match="text or forum"):
        await create_thread(
            CreateThreadParams(parent_channel="lobby", name="x"), guild
        )


@pytest.mark.asyncio
async def test_archive_thread():
    guild, thread = _make_guild_with_thread()
    await archive_thread(ArchiveThreadParams(thread="FAQ"), guild)
    thread.edit.assert_awaited_once()
    assert thread.edit.await_args.kwargs["archived"] is True


@pytest.mark.asyncio
async def test_unarchive_thread():
    guild, thread = _make_guild_with_thread()
    await unarchive_thread(UnarchiveThreadParams(thread="FAQ"), guild)
    assert thread.edit.await_args.kwargs["archived"] is False


@pytest.mark.asyncio
async def test_lock_thread():
    guild, thread = _make_guild_with_thread()
    await lock_thread(LockThreadParams(thread="FAQ"), guild)
    assert thread.edit.await_args.kwargs["locked"] is True


@pytest.mark.asyncio
async def test_archive_thread_unknown_raises():
    guild = MagicMock(spec=discord.Guild)
    guild.threads = []
    with pytest.raises(ValueError, match="not found"):
        await archive_thread(ArchiveThreadParams(thread="ghost"), guild)
