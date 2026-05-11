"""/architect slash command surface."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from architect.bot.architect_command import ArchitectCommand, _format_duration


def _make_events_cog(
    last_executed: dict[int, list[dict]] | None = None,
    stats_overrides: dict | None = None,
) -> MagicMock:
    """Stand-in for the real BotEvents cog — exposes the methods /architect uses."""
    events = MagicMock()
    stats = {
        "started_at": datetime.now(UTC),
        "plans_executed": 7,
        "actions_succeeded": 42,
        "action_errors": 1,
        "rate_limited_actions": 3,
    }
    if stats_overrides:
        stats.update(stats_overrides)
    events.session_stats.return_value = stats
    events.last_executed.side_effect = lambda gid: list(
        (last_executed or {}).get(gid, [])
    )
    events._execute_batch = AsyncMock(return_value=(0, [], 0, []))
    return events


def _make_interaction(guild_id: int = 123, user_id: int = 999) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild_id = guild_id
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.guild = MagicMock()
    interaction.guild.id = guild_id
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


# ── status ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_status_returns_embed_with_counters():
    cog = ArchitectCommand(MagicMock(), _make_events_cog())
    interaction = _make_interaction()
    await cog.status.callback(cog, interaction)
    interaction.response.send_message.assert_awaited_once()
    kwargs = interaction.response.send_message.await_args.kwargs
    embed = kwargs["embed"]
    fields = {f.name: f.value for f in embed.fields}
    assert fields["Plans exec"] == "7"
    assert fields["Actions OK"] == "42"
    assert fields["Errors"] == "1"
    assert fields["Rate-limited"] == "3"
    assert kwargs.get("ephemeral") is True


# ── prefs ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_prefs_empty(monkeypatch, tmp_path):
    from architect.storage import guild_context as gc

    monkeypatch.setattr(gc, "DATA_DIR", tmp_path)
    cog = ArchitectCommand(MagicMock(), _make_events_cog())
    interaction = _make_interaction(guild_id=42)
    await cog.prefs.callback(cog, interaction)
    embed = interaction.response.send_message.await_args.kwargs["embed"]
    fields = {f.name: f.value for f in embed.fields}
    assert "none" in fields["Preferences"]


@pytest.mark.asyncio
async def test_prefs_lists_existing(monkeypatch, tmp_path):
    from architect.storage import guild_context as gc
    from architect.storage.guild_context import GuildContext, save

    monkeypatch.setattr(gc, "DATA_DIR", tmp_path)
    ctx = GuildContext(guild_id=42)
    ctx.record("noms en français", kind="preference")
    ctx.record("user refused AutoMod", kind="decision")
    save(ctx)
    cog = ArchitectCommand(MagicMock(), _make_events_cog())
    interaction = _make_interaction(guild_id=42)
    await cog.prefs.callback(cog, interaction)
    embed = interaction.response.send_message.await_args.kwargs["embed"]
    fields = {f.name: f.value for f in embed.fields}
    assert "noms en français" in fields["Preferences"]
    assert "user refused AutoMod" in fields["Recent decisions"]


@pytest.mark.asyncio
async def test_prefs_clear_removes_entries(monkeypatch, tmp_path):
    from architect.storage import guild_context as gc
    from architect.storage.guild_context import GuildContext, load, save

    monkeypatch.setattr(gc, "DATA_DIR", tmp_path)
    ctx = GuildContext(guild_id=42)
    ctx.record("rule", kind="preference")
    save(ctx)
    cog = ArchitectCommand(MagicMock(), _make_events_cog())
    interaction = _make_interaction(guild_id=42)
    await cog.prefs_clear.callback(cog, interaction)
    interaction.response.send_message.assert_awaited_once()
    loaded = load(42)
    assert loaded is not None
    assert loaded.preferences == []


@pytest.mark.asyncio
async def test_prefs_clear_nothing_to_clear(monkeypatch, tmp_path):
    from architect.storage import guild_context as gc

    monkeypatch.setattr(gc, "DATA_DIR", tmp_path)
    cog = ArchitectCommand(MagicMock(), _make_events_cog())
    interaction = _make_interaction(guild_id=42)
    await cog.prefs_clear.callback(cog, interaction)
    msg = interaction.response.send_message.await_args.args[0]
    assert "Nothing to clear" in msg


# ── snapshots ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_snapshots_lists_recent(monkeypatch, tmp_path):
    from architect.models.snapshot import GuildSnapshot
    from architect.storage import snapshots as snapshots_store

    monkeypatch.setattr(snapshots_store.settings, "data_dir", tmp_path)
    snap = GuildSnapshot()
    snapshots_store.save_pre_exec_snapshot(42, snap, "Refonte", [])
    cog = ArchitectCommand(MagicMock(), _make_events_cog())
    interaction = _make_interaction(guild_id=42)
    await cog.snapshots.callback(cog, interaction)
    embed = interaction.response.send_message.await_args.kwargs["embed"]
    assert "Refonte" in embed.description


@pytest.mark.asyncio
async def test_snapshots_empty_returns_message(monkeypatch, tmp_path):
    from architect.storage import snapshots as snapshots_store

    monkeypatch.setattr(snapshots_store.settings, "data_dir", tmp_path)
    cog = ArchitectCommand(MagicMock(), _make_events_cog())
    interaction = _make_interaction(guild_id=42)
    await cog.snapshots.callback(cog, interaction)
    msg = interaction.response.send_message.await_args.args[0]
    assert "No snapshot" in msg


# ── undo ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_undo_nothing_to_undo():
    cog = ArchitectCommand(MagicMock(), _make_events_cog(last_executed={}))
    interaction = _make_interaction(guild_id=42)
    await cog.undo.callback(cog, interaction)
    msg = interaction.response.send_message.await_args.args[0]
    assert "Nothing to undo" in msg


@pytest.mark.asyncio
async def test_undo_skips_when_no_invertible_actions():
    # edit + delete have no inverse in v1 → empty inverse plan
    events = _make_events_cog(
        last_executed={
            42: [
                {"type": "edit_channel", "params": {"channel": "x", "name": "y"}},
                {"type": "delete_role", "params": {"role": "r"}},
            ]
        }
    )
    cog = ArchitectCommand(MagicMock(), events)
    interaction = _make_interaction(guild_id=42)
    await cog.undo.callback(cog, interaction)
    msg = interaction.response.send_message.await_args.args[0]
    assert "Nothing to undo" in msg


# ── audit ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_posts_kickoff_in_channel():
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.mention = "@architect"
    cog = ArchitectCommand(bot, _make_events_cog())
    interaction = _make_interaction()
    interaction.channel = MagicMock()
    interaction.channel.send = AsyncMock()
    await cog.audit.callback(cog, interaction)
    interaction.response.send_message.assert_awaited_once()
    interaction.channel.send.assert_awaited_once()
    sent = interaction.channel.send.await_args.args[0]
    assert "@architect" in sent
    assert "audit" in sent.lower()
    assert "record_finding" in sent


@pytest.mark.asyncio
async def test_audit_without_channel_returns_error():
    cog = ArchitectCommand(MagicMock(), _make_events_cog())
    interaction = _make_interaction()
    interaction.channel = None
    await cog.audit.callback(cog, interaction)
    msg = interaction.response.send_message.await_args.args[0]
    assert "channel" in msg.lower()


# ── _format_duration helper ─────────────────────────────────────────────────


def test_format_duration_seconds_only():
    assert _format_duration(45) == "45s"


def test_format_duration_minutes_and_seconds():
    assert _format_duration(125) == "2m 5s"


def test_format_duration_hours():
    assert _format_duration(3700) == "1h 1m"
