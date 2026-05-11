from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from architect.agent.events import AgentEvent, ReplyEvent
from architect.bot.events import (
    BotEvents,
    _chunk_text,
    _compute_inverse_plan,
    _format_params,
    _looks_like_creative_turn,
    _serialize_guild,
    _should_use_plan_model,
    build_guild_snapshot,
)
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
    assert "### Channels" in result
    assert "**Gaming**" in result
    assert "**Work**" in result
    assert "#general" in result
    assert "#random" in result
    assert "Voice 1" in result
    assert "[text]" in result
    assert "[voice]" in result
    assert "### Roles" in result
    assert "@Admin" in result
    assert "@Member" in result
    assert "@everyone" not in result


def test_serialize_guild_empty():
    guild = _make_guild()
    result = _serialize_guild(guild)
    # Empty channels list yields "(none)" and empty roles list also "(none)"
    assert "(none)" in result


def test_serialize_guild_explicit_channels_param():
    guild = _make_guild(categories=["Cat1"], text_channels=["chan1"])
    # Pass only a text channel — the category should not appear
    text_ch = MagicMock(spec=discord.TextChannel)
    text_ch.name = "override"
    result = _serialize_guild(guild, channels=[text_ch])
    assert "#override" in result
    assert "Cat1" not in result


def test_serialize_guild_includes_channel_id_and_topic():
    """Rich serialization: channel id and topic must surface so the agent can edit."""
    guild = _make_guild(categories=["Cat"])
    ch = MagicMock(spec=discord.TextChannel)
    ch.name = "rules"
    ch.id = 4242
    ch.topic = "Please read carefully before posting."
    ch.position = 0
    ch.slowmode_delay = 30
    ch.category_id = None
    ch.nsfw = False
    result = _serialize_guild(guild, channels=[ch])
    assert "id=4242" in result
    assert "rules" in result
    assert "Please read carefully" in result
    assert "slowmode=30s" in result


def test_serialize_guild_groups_channels_under_category():
    cat = MagicMock(spec=discord.CategoryChannel)
    cat.name = "Communauté"
    cat.id = 100
    cat.position = 0
    ch = MagicMock(spec=discord.TextChannel)
    ch.name = "general"
    ch.id = 200
    ch.position = 1
    ch.topic = None
    ch.slowmode_delay = 0
    ch.nsfw = False
    ch.category_id = 100
    guild = MagicMock(spec=discord.Guild)
    guild.channels = [cat, ch]
    guild.roles = []
    result = _serialize_guild(guild)
    # The channel must appear nested under the category line.
    lines = result.splitlines()
    cat_idx = next(i for i, line in enumerate(lines) if "Communauté" in line)
    ch_idx = next(i for i, line in enumerate(lines) if "general" in line)
    assert ch_idx > cat_idx
    assert lines[ch_idx].startswith("    -")  # indented child line


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
# _looks_like_creative_turn + _should_use_plan_model
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prompt",
    [
        "restructure le serveur",
        "fais-le plus compact",
        "rends-le plus cozy stp",
        "setup MVP complet",
        "Set up the server please",
        "optimise les channels",
        "simplifie tout ça",
        "réorganise les catégories",
        "merge ces 3 catégories",
        "refonte complète",
        "nettoie un peu",
    ],
)
def test_creative_turn_keywords_detected(prompt: str):
    assert _looks_like_creative_turn(prompt) is True


@pytest.mark.parametrize(
    "prompt",
    [
        "salut",
        "liste les channels",
        "qui peut voir #general ?",
        "supprime ce channel",
        "",
    ],
)
def test_creative_turn_non_matches(prompt: str):
    assert _looks_like_creative_turn(prompt) is False


def test_should_use_plan_model_fresh_history():
    assert _should_use_plan_model([{"role": "user", "content": "anything"}]) is True


def test_should_use_plan_model_follow_up_creative_prompt():
    history = [
        {"role": "user", "content": "setup le serveur"},
        {"role": "assistant", "content": "done"},
        {"role": "user", "content": "rends-le plus compact"},
    ]
    assert _should_use_plan_model(history) is True


def test_should_use_plan_model_follow_up_non_creative_prompt():
    history = [
        {"role": "user", "content": "salut"},
        {"role": "assistant", "content": "yes?"},
        {"role": "user", "content": "qui voit #general ?"},
    ]
    assert _should_use_plan_model(history) is False


def test_should_use_plan_model_mid_tool_call():
    """When the last user entry is a tool_result list, we're inside a loop iteration."""
    history = [
        {"role": "user", "content": "setup"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t1"}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1"}]},
    ]
    assert _should_use_plan_model(history) is False


# ---------------------------------------------------------------------------
# on_message — thread continuation & resilience
# ---------------------------------------------------------------------------


def _make_bot_thread_message(
    *,
    bot_user_id: int = 999,
    thread_owner_id: int = 999,
    content: str = "follow up",
    guild: discord.Guild | None = None,
) -> MagicMock:
    """Build a message whose channel is a discord.Thread owned by the bot."""
    msg = MagicMock(spec=discord.Message)
    author = MagicMock()
    author.bot = False
    author.id = 1234
    msg.author = author
    msg.content = content
    msg.guild = guild
    msg.mentions = []
    msg.reference = None
    msg.reply = AsyncMock()

    thread = MagicMock(spec=discord.Thread)
    thread.id = 77
    thread.owner_id = thread_owner_id
    status_msg = MagicMock()
    status_msg.edit = AsyncMock()
    thread.send = AsyncMock(return_value=status_msg)
    msg.channel = thread
    msg._mock_thread = thread
    msg._mock_status_msg = status_msg
    return msg


@pytest.mark.asyncio
async def test_on_message_in_bot_owned_thread_triggers_without_mention():
    """Messages in a bot-owned thread should be processed even without mention/reply."""
    evt = ReplyEvent(text="ok")
    cog, bot, agent = _make_cog([evt])
    bot.user.id = 999

    guild = _make_guild()
    guild.id = 123456789
    guild.fetch_channels = AsyncMock(return_value=[])

    msg = _make_bot_thread_message(bot_user_id=999, thread_owner_id=999, guild=guild)

    await cog.on_message(msg)

    agent.step.assert_called_once()
    # create_thread MUST NOT be called when already inside a thread
    assert not hasattr(msg, "create_thread") or not getattr(
        msg.create_thread, "called", False
    )


@pytest.mark.asyncio
async def test_on_message_in_foreign_thread_still_requires_mention():
    """A thread NOT owned by the bot should not auto-trigger."""
    cog, bot, agent = _make_cog()
    bot.user.id = 999

    guild = _make_guild()
    guild.id = 123456789

    msg = _make_bot_thread_message(bot_user_id=999, thread_owner_id=555, guild=guild)

    await cog.on_message(msg)

    agent.step.assert_not_called()


@pytest.mark.asyncio
async def test_on_message_history_keyed_by_thread_not_source_channel():
    """First user message and follow-ups must share the same history bucket (thread.id)."""
    evt = ReplyEvent(text="ok")
    cog, bot, agent = _make_cog([evt])
    bot.user.id = 999

    guild = _make_guild()
    guild.id = 123456789
    guild.fetch_channels = AsyncMock(return_value=[])

    msg = _make_message(mentions_bot=True, content="hello", guild=guild)
    msg.mentions = [cog.bot.user]

    await cog.on_message(msg)

    thread_id = msg._mock_thread.id  # 43
    source_channel_id = msg.channel.id  # 42
    assert thread_id != source_channel_id

    # The history must live under the thread id, not the source channel id.
    assert cog._history.get(thread_id), "history should be under thread.id"
    assert not cog._history.get(source_channel_id), (
        "history must NOT be split under source channel.id"
    )


@pytest.mark.asyncio
async def test_create_thread_http_exception_falls_back_to_channel():
    """If create_thread fails with any HTTPException (not just Forbidden), fall back."""
    evt = ReplyEvent(text="ok")
    cog, bot, agent = _make_cog([evt])
    bot.user.id = 999

    guild = _make_guild()
    guild.id = 123456789
    guild.fetch_channels = AsyncMock(return_value=[])

    msg = _make_message(mentions_bot=True, content="hello", guild=guild)
    msg.mentions = [cog.bot.user]
    # Simulate the 50024 error path (HTTPException, not Forbidden)
    response = MagicMock()
    response.status = 400
    msg.create_thread = AsyncMock(
        side_effect=discord.HTTPException(response, {"code": 50024, "message": "x"})
    )
    # Make the source channel usable as a fallback target
    msg.channel.send = AsyncMock(return_value=msg._mock_status_msg)

    await cog.on_message(msg)

    # Should not crash; agent should still have been stepped via the fallback channel.
    agent.step.assert_called_once()


@pytest.mark.asyncio
async def test_readonly_tools_execute_in_parallel():
    """Multiple ReadOnlyToolEvents in one step should run concurrently, not
    serialized — total wall time must be close to max(individual) rather than
    sum(individual)."""
    import asyncio as _asyncio
    import time

    from architect.agent.events import ReadOnlyToolEvent

    evts = [
        ReadOnlyToolEvent(tool_name="list_channels", params={}, tool_use_id="a"),
        ReadOnlyToolEvent(tool_name="list_roles", params={}, tool_use_id="b"),
        ReadOnlyToolEvent(tool_name="check_bot_permissions", params={}, tool_use_id="c"),
    ]
    cog, bot, agent = _make_cog(evts)

    async def slow_execute(tool_name, params, guild, strict=False):
        await _asyncio.sleep(0.5)
        return f"{tool_name}-ok"

    cog._executor.execute = AsyncMock(side_effect=slow_execute)

    # Second step returns nothing → loop ends.
    agent.step = AsyncMock(side_effect=[evts, []])

    guild = _make_guild()
    guild.id = 123456789
    msg = _make_message(mentions_bot=True, content="audit du serveur", guild=guild)
    msg.mentions = [cog.bot.user]

    t0 = time.monotonic()
    await cog.on_message(msg)
    elapsed = time.monotonic() - t0

    # 3 x 0.5s sequential would be ~1.5s; concurrent should be ~0.5s.
    # Allow generous slack but assert clearly under sequential cost.
    assert elapsed < 1.0, f"readonly tools appear to run sequentially ({elapsed:.2f}s)"
    # Each tool was called exactly once.
    assert cog._executor.execute.await_count == 3


@pytest.mark.asyncio
async def test_execute_batch_signals_rate_limit_when_action_is_slow():
    """If an action stays pending past the wait_for threshold, the progress_msg must
    be updated with a rate-limit notice before the action completes."""
    import asyncio as _asyncio

    cog, bot, agent = _make_cog()

    release = _asyncio.Event()

    async def slow_execute(action_type, params, guild, strict=False):
        await release.wait()
        return "done"

    cog._executor.execute = AsyncMock(side_effect=slow_execute)

    progress_msg = MagicMock()
    progress_msg.edit = AsyncMock()

    guild = _make_guild()

    async def runner():
        return await cog._execute_batch(
            [{"type": "create_category", "params": {"name": "X"}}],
            guild,
            progress_msg,
        )

    task = _asyncio.create_task(runner())
    # Wait long enough for the 3s wait_for to time out.
    await _asyncio.sleep(3.2)
    # The rate-limit notice should have been emitted.
    rate_limit_calls = [
        call
        for call in progress_msg.edit.await_args_list
        if call.kwargs.get("embed")
        and "rate-limited" in call.kwargs["embed"].description
    ]
    assert rate_limit_calls, "progress_msg should have been edited with a rate-limit notice"
    release.set()
    success, errors, rolled_back, executed = await task
    assert success == 1
    assert errors == []
    assert len(executed) == 1


@pytest.mark.asyncio
async def test_status_edit_after_channel_deleted_does_not_crash():
    """If a plan deletes the channel hosting status_msg, the final edit must not bubble up."""
    from unittest.mock import patch

    from architect.agent.events import PlanGeneratedEvent
    from architect.bot.views import PlanResult

    actions = [{"type": "delete_text_channel", "params": {"name": "general"}}]
    evt = PlanGeneratedEvent(title="Wipe", actions=actions, tool_use_id="p_wipe")

    cog, bot, agent = _make_cog([evt])

    guild = _make_guild()
    guild.id = 123456789
    guild.fetch_channels = AsyncMock(return_value=[])

    msg = _make_message(mentions_bot=True, content="delete everything", guild=guild)
    msg.mentions = [cog.bot.user]

    status_msg = msg._mock_status_msg
    response = MagicMock()
    response.status = 404
    # Simulate the parent channel being deleted by the plan → every status edit 404s
    status_msg.edit = AsyncMock(
        side_effect=discord.NotFound(response, {"code": 10003, "message": "Unknown Channel"})
    )

    with patch("architect.bot.events.PlanView") as MockPlanView:
        mock_view = MagicMock()
        mock_view.build_embed.return_value = (MagicMock(), None)
        mock_view.wait_result = AsyncMock(return_value=PlanResult.CONFIRMED_ALL)
        MockPlanView.return_value = mock_view

        cog._execute_batch = AsyncMock(return_value=(1, [], 0))

        # Must not raise even though every status_msg.edit raises NotFound.
        await cog.on_message(msg)

    cog._execute_batch.assert_called_once()


@pytest.mark.asyncio
async def test_reply_to_bot_via_cached_message_when_resolved_missing():
    """is_reply_to_bot should work when reference.resolved is None but cached_message is set."""
    evt = ReplyEvent(text="ok")
    cog, bot, agent = _make_cog([evt])
    bot.user.id = 999

    guild = _make_guild()
    guild.id = 123456789
    guild.fetch_channels = AsyncMock(return_value=[])

    msg = _make_message(mentions_bot=False, is_reply_to_bot=False, guild=guild)
    ref = MagicMock(spec=discord.MessageReference)
    ref.message_id = 12345
    ref.resolved = None
    cached = MagicMock(spec=discord.Message)
    cached.author = cog.bot.user
    ref.cached_message = cached
    msg.reference = ref

    await cog.on_message(msg)

    agent.step.assert_called_once()


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

    success, errors, rolled_back, executed = await cog._execute_batch(
        actions, guild, progress, atomic=True
    )

    assert errors and "BadRole" in errors[0]
    assert rolled_back == 2  # Cat1 and ch1 reverted
    assert success == 0  # 2 creations - 2 rollback
    assert executed == []  # rolled-back actions are stripped from the undo list

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

    success, errors, rolled_back, executed = await cog._execute_batch(
        actions, guild, progress, atomic=False
    )

    assert success == 2
    assert len(errors) == 1
    assert rolled_back == 0
    # `executed` only tracks the 2 successful creations, in original order.
    assert [e["params"]["name"] for e in executed] == ["A", "C"]


# ---------------------------------------------------------------------------
# Snapshot + undo plan computation
# ---------------------------------------------------------------------------


def test_build_guild_snapshot_extracts_categories_and_channels():
    guild = _make_guild(
        categories=["Communauté"],
        text_channels=["general", "annonces"],
        roles=["Modo"],
    )
    # Inject explicit positions for snapshot ordering.
    for i, ch in enumerate(guild.channels):
        ch.id = 100 + i
        ch.position = i
        if isinstance(ch, MagicMock) and hasattr(ch, "category_id"):
            ch.category_id = None
    for i, r in enumerate(guild.roles):
        r.id = 200 + i
        r.position = i
    guild.me = MagicMock()
    guild.me.top_role = MagicMock()
    guild.me.top_role.position = 5

    snap = build_guild_snapshot(guild)
    cat_names = [c.name for c in snap.categories]
    ch_names = [c.name for c in snap.channels]
    role_names = [r.name for r in snap.roles]
    assert "Communauté" in cat_names
    assert "general" in ch_names
    assert "Modo" in role_names
    assert "@everyone" not in role_names
    assert snap.bot_top_role_position == 5


def test_compute_inverse_plan_reverses_creates():
    executed = [
        {"type": "create_category", "params": {"name": "Cat"}},
        {"type": "create_text_channel", "params": {"name": "ch"}},
        {"type": "create_role", "params": {"name": "Modo"}},
    ]
    inverse = _compute_inverse_plan(executed)
    # Reversed order — last create undone first.
    assert [a["type"] for a in inverse] == [
        "delete_role",
        "delete_channel",
        "delete_channel",
    ]
    assert inverse[0]["params"] == {"role": "Modo"}


def test_compute_inverse_plan_skips_non_invertible_actions():
    executed = [
        {"type": "edit_channel", "params": {"channel": "x", "name": "y"}},
        {"type": "create_text_channel", "params": {"name": "fresh"}},
        {"type": "delete_channel", "params": {"channel": "old"}},
    ]
    inverse = _compute_inverse_plan(executed)
    # Only the create has a deterministic inverse in v1.
    assert len(inverse) == 1
    assert inverse[0]["type"] == "delete_channel"
    assert inverse[0]["params"] == {"channel": "fresh"}


def test_compute_inverse_plan_empty_when_no_invertible():
    executed = [
        {"type": "edit_channel", "params": {"channel": "x"}},
        {"type": "delete_role", "params": {"role": "y"}},
    ]
    assert _compute_inverse_plan(executed) == []


# ---------------------------------------------------------------------------
# record_preference event handling
# ---------------------------------------------------------------------------


def test_handle_record_preference_persists_and_acks(tmp_path, monkeypatch):
    """RecordPreferenceEvent must write to disk and produce a tool-result ack."""
    from architect.agent.events import RecordPreferenceEvent
    from architect.storage.guild_context import GuildContext

    monkeypatch.setattr(
        "architect.storage.guild_context.DATA_DIR", tmp_path / "data"
    )

    cog, _, _ = _make_cog()
    guild = _make_guild()
    guild.id = 4242

    event = RecordPreferenceEvent(
        text="noms en français", kind="preference", tool_use_id="t1"
    )
    result = cog._handle_record_preference(event, guild, server_context=None)
    assert "recorded" in result
    # Reload from disk to verify persistence.
    from architect.storage.guild_context import load as load_guild

    loaded = load_guild(4242)
    assert isinstance(loaded, GuildContext)
    assert "noms en français" in loaded.preferences


def test_handle_record_preference_skips_duplicate(tmp_path, monkeypatch):
    from architect.agent.events import RecordPreferenceEvent
    from architect.storage.guild_context import GuildContext

    monkeypatch.setattr(
        "architect.storage.guild_context.DATA_DIR", tmp_path / "data"
    )
    cog, _, _ = _make_cog()
    guild = _make_guild()
    guild.id = 4243
    ctx = GuildContext(guild_id=4243)
    ctx.preferences.append("English server")

    event = RecordPreferenceEvent(
        text="English server", kind="preference", tool_use_id="t2"
    )
    result = cog._handle_record_preference(event, guild, server_context=ctx)
    assert "unchanged" in result
    assert ctx.preferences == ["English server"]


# ---------------------------------------------------------------------------
# Parallel execution + progress ticker + pre-exec snapshot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_batch_runs_independent_actions_in_parallel():
    """3 actions in one topological layer must overlap, not serialise."""
    import asyncio as _asyncio

    cog, _, _ = _make_cog()
    in_flight = 0
    peak = 0

    async def slow_execute(tool_name, params, guild, strict=False):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await _asyncio.sleep(0.05)
        in_flight -= 1
        return "ok"

    cog._executor.execute = AsyncMock(side_effect=slow_execute)
    guild = _make_guild()
    progress = MagicMock()
    progress.edit = AsyncMock()
    # 3 independent role creates → one layer of size 3 → all run together
    actions = [
        {"type": "create_role", "params": {"name": "A"}},
        {"type": "create_role", "params": {"name": "B"}},
        {"type": "create_role", "params": {"name": "C"}},
    ]
    success, errors, _, executed = await cog._execute_batch(actions, guild, progress)
    assert success == 3
    assert errors == []
    assert peak == 3  # all three were in flight at the same time
    assert [a["params"]["name"] for a in executed] == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_execute_batch_serialises_dependent_layers():
    """A category create blocks the channel creates that depend on it."""
    import asyncio as _asyncio

    cog, _, _ = _make_cog()
    call_order: list[str] = []

    async def fake_execute(tool_name, params, guild, strict=False):
        call_order.append(params.get("name") or params.get("channel") or "?")
        await _asyncio.sleep(0.01)
        return "ok"

    cog._executor.execute = AsyncMock(side_effect=fake_execute)
    guild = _make_guild()
    progress = MagicMock()
    progress.edit = AsyncMock()
    actions = [
        {"type": "create_category", "params": {"name": "Cat"}},
        {"type": "create_text_channel", "params": {"name": "a", "category": "Cat"}},
        {"type": "create_text_channel", "params": {"name": "b", "category": "Cat"}},
    ]
    success, _, _, _ = await cog._execute_batch(actions, guild, progress)
    assert success == 3
    # First call must be the category; the two channels follow in any order.
    assert call_order[0] == "Cat"
    assert set(call_order[1:]) == {"a", "b"}


@pytest.mark.asyncio
async def test_progress_ticker_emits_at_least_once_during_long_batch():
    """The ticker must refresh progress_msg while the batch is still running."""
    import asyncio as _asyncio

    cog, _, _ = _make_cog()
    release = _asyncio.Event()

    async def hold_until_release(tool_name, params, guild, strict=False):
        await release.wait()
        return "ok"

    cog._executor.execute = AsyncMock(side_effect=hold_until_release)
    guild = _make_guild()
    progress = MagicMock()
    progress.edit = AsyncMock()
    actions = [{"type": "create_role", "params": {"name": "X"}}]

    async def runner():
        return await cog._execute_batch(actions, guild, progress)

    task = _asyncio.create_task(runner())
    await _asyncio.sleep(1.3)  # ticker fires every ~1s
    assert progress.edit.await_count >= 1
    release.set()
    success, _, _, _ = await task
    assert success == 1


@pytest.mark.asyncio
async def test_pre_exec_snapshot_persisted_before_execution(tmp_path, monkeypatch):
    """After the user confirms a plan, a JSON snapshot must land on disk."""
    from architect.agent.events import PlanGeneratedEvent
    from architect.bot.views import PlanResult
    from architect.storage import snapshots as snapshots_store

    monkeypatch.setattr(snapshots_store.settings, "data_dir", tmp_path)
    from unittest.mock import patch

    actions = [{"type": "create_role", "params": {"name": "Modo"}}]
    evt = PlanGeneratedEvent(title="Add Modo", actions=actions, tool_use_id="p_modo")
    cog, _, _ = _make_cog([evt])

    guild = _make_guild(roles=["Existing"])
    guild.id = 123456789  # must match conftest's DISCORD_GUILD_ID
    guild.fetch_automod_rules = AsyncMock(return_value=[])

    msg = _make_message(mentions_bot=True, content="add modo", guild=guild)
    msg.mentions = [cog.bot.user]

    from architect.bot.views import UndoResult

    with (
        patch("architect.bot.events.PlanView") as MockPlanView,
        patch("architect.bot.events.UndoView") as MockUndoView,
    ):
        view = MagicMock()
        view.build_embed.return_value = (MagicMock(), None)
        view.wait_result = AsyncMock(return_value=PlanResult.CONFIRMED_ALL)
        MockPlanView.return_value = view
        undo = MagicMock()
        undo.wait_result = AsyncMock(return_value=(UndoResult.CANCELLED, None))
        MockUndoView.return_value = undo
        await cog.on_message(msg)

    snapshots_dir = tmp_path / "snapshots"
    assert snapshots_dir.exists()
    files = list(snapshots_dir.glob(f"{guild.id}_*.json"))
    assert len(files) == 1
    import json as _json

    payload = _json.loads(files[0].read_text())
    assert payload["plan_title"] == "Add Modo"
    assert payload["plan_actions"][0]["params"]["name"] == "Modo"
    assert any(r["name"] == "Existing" for r in payload["snapshot"]["roles"])
