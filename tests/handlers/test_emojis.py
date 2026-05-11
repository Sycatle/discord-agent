"""Coverage for emoji and sticker handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from architect.executor.handlers.emojis import (
    create_emoji,
    delete_emoji,
    delete_sticker,
    rename_emoji,
)
from architect.models.params.emojis import (
    CreateEmojiParams,
    DeleteEmojiParams,
    DeleteStickerParams,
    RenameEmojiParams,
)


def _make_guild_with_emoji(name: str = "thinking") -> tuple[MagicMock, MagicMock]:
    guild = MagicMock(spec=discord.Guild)
    emoji = MagicMock()
    emoji.name = name
    emoji.id = 99
    emoji.delete = AsyncMock()
    emoji.edit = AsyncMock()
    guild.emojis = [emoji]
    guild.create_custom_emoji = AsyncMock(return_value=emoji)
    return guild, emoji


@pytest.mark.asyncio
async def test_delete_emoji():
    guild, emoji = _make_guild_with_emoji()
    result = await delete_emoji(DeleteEmojiParams(emoji_name="thinking"), guild)
    emoji.delete.assert_awaited_once()
    assert "thinking" in result


@pytest.mark.asyncio
async def test_delete_emoji_not_found():
    guild = MagicMock(spec=discord.Guild)
    guild.emojis = []
    with pytest.raises(ValueError, match="not found"):
        await delete_emoji(DeleteEmojiParams(emoji_name="ghost"), guild)


@pytest.mark.asyncio
async def test_rename_emoji():
    guild, emoji = _make_guild_with_emoji()
    await rename_emoji(
        RenameEmojiParams(old_name="thinking", new_name="brain"), guild
    )
    emoji.edit.assert_awaited_once()
    assert emoji.edit.await_args.kwargs["name"] == "brain"


@pytest.mark.asyncio
async def test_create_emoji_downloads_image():
    guild, emoji = _make_guild_with_emoji()
    with patch(
        "architect.executor.handlers.emojis._fetch_image",
        new=AsyncMock(return_value=b"png-bytes"),
    ):
        result = await create_emoji(
            CreateEmojiParams(name="thinking", image_url="http://x/y.png"),
            guild,
        )
    guild.create_custom_emoji.assert_awaited_once()
    kwargs = guild.create_custom_emoji.await_args.kwargs
    assert kwargs["name"] == "thinking"
    assert kwargs["image"] == b"png-bytes"
    assert "thinking" in result


@pytest.mark.asyncio
async def test_delete_sticker():
    guild = MagicMock(spec=discord.Guild)
    sticker = MagicMock()
    sticker.name = "wow"
    sticker.delete = AsyncMock()
    guild.stickers = [sticker]
    await delete_sticker(DeleteStickerParams(sticker_name="wow"), guild)
    sticker.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_sticker_not_found():
    guild = MagicMock(spec=discord.Guild)
    guild.stickers = []
    with pytest.raises(ValueError, match="not found"):
        await delete_sticker(DeleteStickerParams(sticker_name="ghost"), guild)
