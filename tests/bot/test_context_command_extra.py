"""Coverage for ContextModal.on_submit and the no-guild branches of /context."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from architect.bot.context_command import ContextCommand, ContextModal


@pytest.mark.asyncio
async def test_modal_on_submit_no_guild_id_is_noop(monkeypatch, tmp_path):
    monkeypatch.setattr("architect.storage.guild_context.DATA_DIR", tmp_path / "d")
    modal = ContextModal(existing=None)
    interaction = AsyncMock()
    interaction.guild_id = None
    await modal.on_submit(interaction)
    interaction.response.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_modal_on_submit_persists_and_acks(monkeypatch, tmp_path):
    monkeypatch.setattr("architect.storage.guild_context.DATA_DIR", tmp_path / "d")
    modal = ContextModal(existing=None)
    # TextInputs default to empty strings when no existing context
    interaction = AsyncMock()
    interaction.guild_id = 42
    await modal.on_submit(interaction)
    interaction.response.send_message.assert_called_once()
    embed = interaction.response.send_message.call_args.kwargs.get("embed")
    assert embed is not None
    assert "saved" in embed.title.lower()


@pytest.mark.asyncio
async def test_context_set_outside_guild_replies(monkeypatch, tmp_path):
    monkeypatch.setattr("architect.storage.guild_context.DATA_DIR", tmp_path / "d")
    cog = ContextCommand(MagicMock())
    interaction = AsyncMock()
    interaction.guild_id = None
    await cog.context_set.callback(cog, interaction)
    interaction.response.send_message.assert_called_once()
    assert "inside a server" in interaction.response.send_message.call_args.args[0].lower()


@pytest.mark.asyncio
async def test_context_show_outside_guild_replies(monkeypatch, tmp_path):
    monkeypatch.setattr("architect.storage.guild_context.DATA_DIR", tmp_path / "d")
    cog = ContextCommand(MagicMock())
    interaction = AsyncMock()
    interaction.guild_id = None
    await cog.context_show.callback(cog, interaction)
    interaction.response.send_message.assert_called_once()
    assert "inside a server" in interaction.response.send_message.call_args.args[0].lower()
