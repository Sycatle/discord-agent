"""Emoji and sticker handlers (create / delete / rename emoji ; delete sticker)."""

from __future__ import annotations

import aiohttp
import discord

from architect.executor._resolve import resolve_role
from architect.models.params.emojis import (
    CreateEmojiParams,
    DeleteEmojiParams,
    DeleteStickerParams,
    RenameEmojiParams,
)

_MAX_EMOJI_BYTES = 256 * 1024  # Discord's hard limit


async def _fetch_image(url: str) -> bytes:
    async with aiohttp.ClientSession() as session, session.get(url) as resp:
        resp.raise_for_status()
        data = await resp.read()
        if len(data) > _MAX_EMOJI_BYTES:
            raise ValueError(
                f"Image too large ({len(data)} bytes > {_MAX_EMOJI_BYTES} byte cap)"
            )
        return data


async def create_emoji(params: CreateEmojiParams, guild: discord.Guild) -> str:
    image = await _fetch_image(params.image_url)
    roles: list[discord.Role] = []
    if params.roles_allowed:
        roles = [resolve_role(guild, r) for r in params.roles_allowed]
    emoji = await guild.create_custom_emoji(
        name=params.name,
        image=image,
        roles=roles,
        reason=params.reason,
    )
    return f"Emoji created: :{emoji.name}: ({emoji.id})"


def _find_emoji(guild: discord.Guild, name: str) -> discord.Emoji | None:
    return next((e for e in guild.emojis if e.name == name), None)


async def delete_emoji(params: DeleteEmojiParams, guild: discord.Guild) -> str:
    emoji = _find_emoji(guild, params.emoji_name)
    if emoji is None:
        raise ValueError(f"Emoji not found: {params.emoji_name!r}")
    await emoji.delete(reason=params.reason)
    return f"Emoji deleted: :{params.emoji_name}:"


async def rename_emoji(params: RenameEmojiParams, guild: discord.Guild) -> str:
    emoji = _find_emoji(guild, params.old_name)
    if emoji is None:
        raise ValueError(f"Emoji not found: {params.old_name!r}")
    await emoji.edit(name=params.new_name, reason=params.reason)
    return f"Emoji renamed: :{params.old_name}: → :{params.new_name}:"


async def delete_sticker(params: DeleteStickerParams, guild: discord.Guild) -> str:
    sticker = next(
        (s for s in guild.stickers if s.name == params.sticker_name), None
    )
    if sticker is None:
        raise ValueError(f"Sticker not found: {params.sticker_name!r}")
    await sticker.delete(reason=params.reason)
    return f"Sticker deleted: {params.sticker_name}"
