from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from architect.agent.events import AgentEvent, ReplyEvent
from architect.bot.events import BotEvents, _chunk_text, _format_params, _serialize_guild
from architect.bot.history import ConversationHistory

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
    for name in categories or []:
        c = MagicMock(spec=discord.CategoryChannel)
        c.name = name
        cats.append(c)

    texts = []
    for name in text_channels or []:
        c = MagicMock(spec=discord.TextChannel)
        c.name = name
        texts.append(c)

    voices = []
    for name in voice_channels or []:
        c = MagicMock(spec=discord.VoiceChannel)
        c.name = name
        voices.append(c)

    all_channels = cats + texts + voices
    guild.channels = all_channels

    role_mocks = []
    for name in roles or []:
        r = MagicMock(spec=discord.Role)
        r.name = name
        role_mocks.append(r)
    # always add @everyone
    everyone = MagicMock(spec=discord.Role)
    everyone.name = "@everyone"
    guild.roles = [*role_mocks, everyone]

    return guild


def _make_cog(
    agent_events: list[AgentEvent] | None = None,
) -> tuple[BotEvents, MagicMock, MagicMock]:
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
    assert (
        _format_params({"name": "Gaming", "mentionable": True}) == "name: Gaming, mentionable: True"
    )


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

    status_msg = MagicMock()
    status_msg.edit = AsyncMock()

    thread = MagicMock()
    thread.send = AsyncMock(return_value=status_msg)
    thread.id = 43

    msg.create_thread = AsyncMock(return_value=thread)
    msg._mock_thread = thread
    msg._mock_status_msg = status_msg

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
async def test_guild_mismatch_replies():
    cog, bot, agent = _make_cog()
    bot_user = MagicMock(spec=discord.ClientUser)
    bot_user.id = 999
    cog.bot.user = bot_user

    guild = _make_guild()
    guild.id = 999999999  # different from DISCORD_GUILD_ID=123456789 in conftest

    msg = _make_message(mentions_bot=True, content="bonjour", guild=guild)
    msg.mentions = [bot_user]
    await cog.on_message(msg)

    msg.reply.assert_called_once()
    assert "not configured" in str(msg.reply.call_args).lower()
    agent.step.assert_not_called()


@pytest.mark.asyncio
async def test_on_message_empty_prompt_after_mention():
    cog, bot, agent = _make_cog()
    bot_user = MagicMock(spec=discord.ClientUser)
    bot_user.id = 999
    cog.bot.user = bot_user

    msg = _make_message(mentions_bot=True, content="<@999>")
    msg.mentions = [bot_user]
    await cog.on_message(msg)

    msg.reply.assert_called_once_with("What is your request?")
    agent.step.assert_not_called()


# ---------------------------------------------------------------------------
# PlanGeneratedEvent — batch execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_generated_event_confirm_all():
    """PlanGeneratedEvent → PlanView shown → user clicks Confirm All → batch executed."""
    from unittest.mock import patch

    from architect.agent.events import PlanGeneratedEvent
    from architect.bot.views import PlanResult

    actions = [
        {"type": "create_category", "params": {"name": "General"}},
        {"type": "create_text_channel", "params": {"name": "general", "category": "General"}},
    ]
    evt = PlanGeneratedEvent(title="Test Plan", actions=actions, tool_use_id="plan1")

    cog, bot, agent = _make_cog([evt])

    guild = _make_guild()
    guild.id = 123456789
    guild.fetch_channels = AsyncMock(return_value=[])

    msg = _make_message(mentions_bot=True, content="create a server", guild=guild)
    msg.author.id = 42
    msg.mentions = [cog.bot.user]  # must be same object as cog.bot.user for `in` check
    msg.channel.typing.return_value.__aenter__ = AsyncMock(return_value=None)
    msg.channel.typing.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("architect.bot.events.PlanView") as MockPlanView:
        mock_view_instance = MagicMock()
        mock_view_instance.build_embed.return_value = (MagicMock(), None)
        mock_view_instance.wait_result = AsyncMock(return_value=PlanResult.CONFIRMED_ALL)
        MockPlanView.return_value = mock_view_instance

        cog._execute_batch = AsyncMock(return_value=(2, [], 0))

        await cog.on_message(msg)

    cog._execute_batch.assert_called_once()
    call_args = cog._execute_batch.call_args
    assert call_args[0][0] == actions

    thread = msg._mock_thread
    status_msg = msg._mock_status_msg
    # thread.send: 1x initial status + 1x plan embed + 1x progress_msg
    assert thread.send.call_count == 3
    # status_msg.edit: 1x "Plan generated..." + 1x final result
    assert status_msg.edit.call_count == 2


@pytest.mark.asyncio
async def test_plan_generated_event_cancelled():
    from unittest.mock import patch

    from architect.agent.events import PlanGeneratedEvent
    from architect.bot.views import PlanResult

    evt = PlanGeneratedEvent(title="Test", actions=[], tool_use_id="p2")
    cog, bot, agent = _make_cog([evt])

    guild = _make_guild()
    guild.id = 123456789
    guild.fetch_channels = AsyncMock(return_value=[])

    msg = _make_message(mentions_bot=True, content="test", guild=guild)
    msg.mentions = [cog.bot.user]  # must be same object as cog.bot.user for `in` check
    msg.channel.typing.return_value.__aenter__ = AsyncMock(return_value=None)
    msg.channel.typing.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("architect.bot.events.PlanView") as MockPlanView:
        mock_view = MagicMock()
        mock_view.build_embed.return_value = (MagicMock(), None)
        mock_view.wait_result = AsyncMock(return_value=PlanResult.CANCELLED)
        MockPlanView.return_value = mock_view

        await cog.on_message(msg)

    status_msg = msg._mock_status_msg
    assert status_msg.edit.call_count == 2
    last_embed = status_msg.edit.call_args.kwargs.get("embed")
    assert isinstance(last_embed, discord.Embed)
    assert "cancelled" in last_embed.description.lower()


# ---------------------------------------------------------------------------
# _chunk_text — unit tests
# ---------------------------------------------------------------------------


def test_chunk_text_short_returns_single():
    text = "Bonjour !"
    assert _chunk_text(text) == [text]


def test_chunk_text_at_limit_returns_single():
    text = "x" * 4000
    result = _chunk_text(text)
    assert result == [text]


def test_chunk_text_over_limit_splits():
    text = "x" * 4001
    result = _chunk_text(text)
    assert len(result) == 2
    assert result[0] == "x" * 4000
    assert result[1] == "x"


def test_chunk_text_paragraph_boundary():
    # Two paragraphs that together exceed limit but each is below limit.
    para_a = "a" * 3000
    para_b = "b" * 3000
    text = para_a + "\n\n" + para_b
    result = _chunk_text(text)
    assert len(result) == 2
    assert result[0] == para_a
    assert result[1] == para_b


def test_chunk_text_line_boundary():
    # A single paragraph where two lines together exceed limit but each is below.
    line_a = "a" * 3000
    line_b = "b" * 3000
    text = line_a + "\n" + line_b
    result = _chunk_text(text)
    assert len(result) == 2
    assert result[0] == line_a
    assert result[1] == line_b


def test_chunk_text_hard_cut():
    # A single line > 2 * limit forces hard cut into multiple chunks.
    line = "z" * 12001
    result = _chunk_text(line, limit=4000)
    assert all(len(c) <= 4000 for c in result)
    assert "".join(result) == line


def test_chunk_text_custom_limit():
    text = "hello world"
    result = _chunk_text(text, limit=5)
    assert all(len(c) <= 5 for c in result)
    assert "".join(result) == text


def test_chunk_text_empty_string():
    assert _chunk_text("") == [""]


# ---------------------------------------------------------------------------
# ReplyEvent — always uses embed now
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reply_event_short_text_uses_embed():
    """Short ReplyEvent (< 280 chars, no newline) now always sends embed."""

    evt = ReplyEvent(text="Bonjour !")
    cog, bot, agent = _make_cog([evt])

    guild = _make_guild()
    guild.id = 123456789
    guild.fetch_channels = AsyncMock(return_value=[])

    msg = _make_message(mentions_bot=True, content="salut", guild=guild)
    msg.mentions = [cog.bot.user]
    msg.channel.typing.return_value.__aenter__ = AsyncMock(return_value=None)
    msg.channel.typing.return_value.__aexit__ = AsyncMock(return_value=False)

    await cog.on_message(msg)

    status_msg = msg._mock_status_msg
    status_msg.edit.assert_called_once()
    embed_arg = status_msg.edit.call_args.kwargs.get("embed")
    assert isinstance(embed_arg, discord.Embed)


@pytest.mark.asyncio
async def test_reply_event_long_text_sends_multiple_chunks():
    """ReplyEvent with text > _EMBED_LIMIT sends multiple messages."""
    from architect.bot.events import _EMBED_LIMIT

    long_text = "a" * (_EMBED_LIMIT + 1)
    evt = ReplyEvent(text=long_text)
    cog, bot, agent = _make_cog([evt])

    guild = _make_guild()
    guild.id = 123456789
    guild.fetch_channels = AsyncMock(return_value=[])

    msg = _make_message(mentions_bot=True, content="hello", guild=guild)
    msg.mentions = [cog.bot.user]
    msg.channel.typing.return_value.__aenter__ = AsyncMock(return_value=None)
    msg.channel.typing.return_value.__aexit__ = AsyncMock(return_value=False)

    await cog.on_message(msg)

    status_msg = msg._mock_status_msg
    thread = msg._mock_thread
    # First chunk via status_msg.edit, second chunk via thread.send
    status_msg.edit.assert_called_once()
    edit_embed = status_msg.edit.call_args.kwargs.get("embed")
    assert isinstance(edit_embed, discord.Embed)
    # thread.send: 1x initial status_msg + 1x overflow chunk
    assert thread.send.call_count == 2
    overflow_embed = thread.send.call_args.kwargs.get("embed")
    assert isinstance(overflow_embed, discord.Embed)


# ── Atomic batch / rollback ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_batch_atomic_rolls_back_creates_on_failure():
    """In atomic mode, an error on action #3 must roll back the 2 prior creations."""
    from architect.executor.executor import ExecuteError

    cog, _, _ = _make_cog()

    # Executor returns OK for the first 2 actions, error on the 3rd.
    call_log: list[tuple[str, dict]] = []

    async def fake_execute(tool_name, params, guild, *, strict=False):
        call_log.append((tool_name, params))
        if tool_name == "create_role" and params.get("name") == "BadRole":
            if strict:
                raise ExecuteError("Missing permission: `manage_roles`.")
            return "Missing permission: `manage_roles`."
        return f"{tool_name} ok"

    cog._executor.execute = AsyncMock(side_effect=fake_execute)

    guild = _make_guild()
    progress = MagicMock()
    progress.edit = AsyncMock()

    actions = [
        {"type": "create_category", "params": {"name": "Cat1"}},
        {"type": "create_text_channel", "params": {"name": "ch1"}},
        {"type": "create_role", "params": {"name": "BadRole"}},
    ]

    success, errors, rolled_back = await cog._execute_batch(actions, guild, progress, atomic=True)

    assert errors and "BadRole" in errors[0]
    assert rolled_back == 2  # Cat1 and ch1 reverted
    assert success == 0  # 2 creations - 2 rollback

    inverse_calls = [c for c in call_log if c[0] in ("delete_channel", "delete_role")]
    assert len(inverse_calls) == 2
    # Ordre inverse : ch1 d'abord, puis Cat1
    assert inverse_calls[0] == ("delete_channel", {"channel": "ch1"})
    assert inverse_calls[1] == ("delete_channel", {"channel": "Cat1"})


@pytest.mark.asyncio
async def test_execute_batch_non_atomic_continues_on_failure():
    """Without atomic mode, execution continues after an error, no rollback."""
    from architect.executor.executor import ExecuteError

    cog, _, _ = _make_cog()

    async def fake_execute(tool_name, params, guild, *, strict=False):
        if params.get("name") == "Bad":
            if strict:
                raise ExecuteError("boom")
            return "boom"
        return "ok"

    cog._executor.execute = AsyncMock(side_effect=fake_execute)
    guild = _make_guild()
    progress = MagicMock()
    progress.edit = AsyncMock()

    actions = [
        {"type": "create_category", "params": {"name": "A"}},
        {"type": "create_role", "params": {"name": "Bad"}},
        {"type": "create_text_channel", "params": {"name": "C"}},
    ]

    success, errors, rolled_back = await cog._execute_batch(actions, guild, progress, atomic=False)

    assert success == 2
    assert len(errors) == 1
    assert rolled_back == 0
