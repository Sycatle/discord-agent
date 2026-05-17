"""Multi-guild behavior: stats isolation, channel locking, whitelist guards."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from architect.bot.architect_command import ArchitectCommand
from architect.bot.context_command import ContextCommand
from architect.bot.events import BotEvents
from architect.bot.history import ConversationHistory


def _make_cog() -> BotEvents:
    bot = MagicMock()
    bot.user = MagicMock(spec=discord.ClientUser)
    bot.user.id = 999
    return BotEvents(
        bot=bot,
        agent=MagicMock(),
        executor=MagicMock(),
        history=ConversationHistory(),
    )


def _make_interaction(guild_id: int | None) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild_id = guild_id
    interaction.guild = MagicMock() if guild_id is not None else None
    if interaction.guild is not None:
        interaction.guild.id = guild_id
    interaction.user = MagicMock()
    interaction.user.id = 1
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.channel = MagicMock()
    interaction.channel.send = AsyncMock()
    return interaction


# ── Per-guild session stats ─────────────────────────────────────────────────


def test_session_stats_isolated_per_guild():
    cog = _make_cog()
    a = cog.session_stats(42)
    b = cog.session_stats(4242)
    assert a is not b
    cog._stats_for(42)["plans_executed"] = 5
    cog._stats_for(4242)["plans_executed"] = 9
    assert cog.session_stats(42)["plans_executed"] == 5
    assert cog.session_stats(4242)["plans_executed"] == 9


def test_session_stats_initializes_counters_to_zero():
    cog = _make_cog()
    stats = cog.session_stats(123)
    assert stats["plans_executed"] == 0
    assert stats["actions_succeeded"] == 0
    assert stats["action_errors"] == 0
    assert stats["rate_limited_actions"] == 0


def test_session_stats_shared_started_at_across_guilds():
    """All guilds inherit the cog's start time so /architect status uptime
    remains meaningful regardless of when a guild first appeared."""
    cog = _make_cog()
    assert cog.session_stats(1)["started_at"] == cog.session_stats(2)["started_at"]


# ── Channel-level lock ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lock_for_returns_same_instance_per_channel():
    cog = _make_cog()
    lock_a = cog._lock_for(100)
    lock_b = cog._lock_for(100)
    lock_c = cog._lock_for(200)
    assert lock_a is lock_b
    assert lock_a is not lock_c


@pytest.mark.asyncio
async def test_lock_serializes_concurrent_acquirers():
    cog = _make_cog()
    order: list[str] = []

    async def hold(name: str, delay: float) -> None:
        async with cog._lock_for(777):
            order.append(f"{name}-in")
            await asyncio.sleep(delay)
            order.append(f"{name}-out")

    await asyncio.gather(hold("A", 0.02), hold("B", 0.0))
    # B can only enter once A has fully released the lock.
    assert order == ["A-in", "A-out", "B-in", "B-out"]


# ── Slash command whitelist guards ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_architect_status_rejects_non_whitelisted_guild():
    cog = ArchitectCommand(MagicMock(), MagicMock())
    interaction = _make_interaction(guild_id=999999999)  # not in whitelist
    await cog.status.callback(cog, interaction)
    msg = interaction.response.send_message.await_args.args[0]
    assert "not configured" in msg.lower()


@pytest.mark.asyncio
async def test_architect_status_uses_per_guild_stats():
    events = MagicMock()
    events.session_stats.return_value = {
        "started_at": None,
        "plans_executed": 11,
        "actions_succeeded": 0,
        "action_errors": 0,
        "rate_limited_actions": 0,
    }
    cog = ArchitectCommand(MagicMock(), events)
    interaction = _make_interaction(guild_id=42)
    await cog.status.callback(cog, interaction)
    events.session_stats.assert_called_once_with(42)


@pytest.mark.asyncio
async def test_context_show_rejects_non_whitelisted_guild():
    cog = ContextCommand(MagicMock())
    interaction = _make_interaction(guild_id=999999999)
    await cog.context_show.callback(cog, interaction)
    msg = interaction.response.send_message.await_args.args[0]
    assert "not configured" in msg.lower()


@pytest.mark.asyncio
async def test_context_show_rejects_dm():
    cog = ContextCommand(MagicMock())
    interaction = _make_interaction(guild_id=None)
    await cog.context_show.callback(cog, interaction)
    msg = interaction.response.send_message.await_args.args[0]
    assert "server" in msg.lower()
