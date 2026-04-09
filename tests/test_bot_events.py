from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import discord
import pytest

from architect.bot.events import BotEvents, _format_params, _serialize_guild
from architect.bot.history import ConversationHistory
from architect.agent.events import AgentEvent, ReplyEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_guild(
    categories: list[str] | None = None,
    text_channels: list[str] | None = None,
    voice_channels: list[str] | None = None,
    roles: list[str] | None = None,
) -> MagicMock:
    guild = MagicMock(spec=discord.Guild)

    cats = []
    for name in (categories or []):
        c = MagicMock(spec=discord.CategoryChannel)
        c.name = name
        cats.append(c)

    texts = []
    for name in (text_channels or []):
        c = MagicMock(spec=discord.TextChannel)
        c.name = name
        texts.append(c)

    voices = []
    for name in (voice_channels or []):
        c = MagicMock(spec=discord.VoiceChannel)
        c.name = name
        voices.append(c)

    all_channels = cats + texts + voices
    guild.channels = all_channels

    role_mocks = []
    for name in (roles or []):
        r = MagicMock(spec=discord.Role)
        r.name = name
        role_mocks.append(r)
    # always add @everyone
    everyone = MagicMock(spec=discord.Role)
    everyone.name = "@everyone"
    guild.roles = role_mocks + [everyone]

    return guild


def _make_cog(agent_events: list[AgentEvent] | None = None) -> tuple[BotEvents, MagicMock, MagicMock]:
    """Returns (cog, mock_bot, mock_agent)."""
    bot = MagicMock(spec=commands_Bot())
    bot.user = MagicMock(spec=discord.ClientUser)
    bot.user.id = 999

    agent = MagicMock()
    agent.step = AsyncMock(return_value=agent_events or [])

    executor = MagicMock()
    executor.execute = AsyncMock(return_value="done")

    history = ConversationHistory()
    cog = BotEvents(bot=bot, agent=agent, executor=executor, history=history)
    return cog, bot, agent


def commands_Bot():
    from discord.ext import commands
    return commands.Bot


# ---------------------------------------------------------------------------
# Unit tests — pure functions
# ---------------------------------------------------------------------------

def test_serialize_guild_all_fields():
    guild = _make_guild(
        categories=["Gaming", "Work"],
        text_channels=["general", "random"],
        voice_channels=["Voice 1"],
        roles=["Admin", "Member"],
    )
    result = _serialize_guild(guild)
    assert "Categories: Gaming, Work" in result
    assert "Text channels: #general, #random" in result
    assert "Voice channels: Voice 1" in result
    assert "Roles: Admin, Member" in result
    assert "@everyone" not in result


def test_serialize_guild_empty():
    guild = _make_guild()
    result = _serialize_guild(guild)
    assert "none" in result


def test_serialize_guild_explicit_channels_param():
    guild = _make_guild(categories=["Cat1"], text_channels=["chan1"])
    # Pass only a text channel — category should not appear
    text_ch = MagicMock(spec=discord.TextChannel)
    text_ch.name = "override"
    result = _serialize_guild(guild, channels=[text_ch])
    assert "#override" in result
    assert "Cat1" not in result


def test_format_params_simple():
    assert _format_params({"name": "Gaming", "mentionable": True}) == "name: Gaming, mentionable: True"


def test_format_params_list_value():
    result = _format_params({"allow": ["read_messages", "send_messages"]})
    assert result == "allow: [read_messages, send_messages]"


def test_format_params_empty():
    assert _format_params({}) == ""


# ---------------------------------------------------------------------------
# on_message — basic filtering
# ---------------------------------------------------------------------------

def _make_message(
    *,
    is_bot: bool = False,
    mentions_bot: bool = False,
    is_reply_to_bot: bool = False,
    content: str = "hello",
    guild: discord.Guild | None = None,
    bot_user_id: int = 999,
) -> MagicMock:
    msg = MagicMock(spec=discord.Message)
    author = MagicMock()
    author.bot = is_bot
    author.id = 1234
    msg.author = author
    msg.content = content
    msg.guild = guild

    bot_user = MagicMock(spec=discord.ClientUser)
    bot_user.id = bot_user_id
    msg.mentions = [bot_user] if mentions_bot else []

    if is_reply_to_bot:
        ref = MagicMock(spec=discord.MessageReference)
        resolved = MagicMock(spec=discord.Message)
        resolved.author = bot_user
        ref.resolved = resolved
        msg.reference = ref
    else:
        msg.reference = None

    msg.channel = MagicMock()
    msg.channel.id = 42
    msg.channel.send = AsyncMock()
    msg.reply = AsyncMock()

    return msg


@pytest.mark.asyncio
async def test_on_message_ignores_bots():
    cog, bot, agent = _make_cog()
    bot.user = MagicMock(spec=discord.ClientUser)
    bot.user.id = 999
    msg = _make_message(is_bot=True, mentions_bot=True)
    await cog.on_message(msg)
    agent.step.assert_not_called()


@pytest.mark.asyncio
async def test_on_message_ignores_non_mention_non_reply():
    cog, bot, agent = _make_cog()
    bot.user = MagicMock(spec=discord.ClientUser)
    bot.user.id = 999
    msg = _make_message(mentions_bot=False, is_reply_to_bot=False, content="hey")
    await cog.on_message(msg)
    agent.step.assert_not_called()


@pytest.mark.asyncio
async def test_on_message_empty_prompt_after_mention():
    cog, bot, agent = _make_cog()
    bot_user = MagicMock(spec=discord.ClientUser)
    bot_user.id = 999
    cog.bot.user = bot_user

    msg = _make_message(mentions_bot=True, content=f"<@999>")
    msg.mentions = [bot_user]
    await cog.on_message(msg)

    msg.reply.assert_called_once_with("Quelle est ta demande ?")
    agent.step.assert_not_called()
