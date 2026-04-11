import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from architect.bot.context_command import ContextCommand
from architect.storage.guild_context import GuildContext


def make_interaction(guild_id: int = 42, has_manage_guild: bool = True) -> MagicMock:
    interaction = AsyncMock()
    interaction.guild_id = guild_id
    interaction.user = MagicMock()
    interaction.user.guild_permissions = MagicMock()
    interaction.user.guild_permissions.manage_guild = has_manage_guild
    interaction.response = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_context_set_sends_modal_when_authorized(tmp_path, monkeypatch):
    monkeypatch.setattr("architect.storage.guild_context.DATA_DIR", tmp_path / "data")
    bot = MagicMock()
    cog = ContextCommand(bot)
    interaction = make_interaction(has_manage_guild=True)

    await cog.context_set.callback(cog, interaction)

    interaction.response.send_modal.assert_called_once()


@pytest.mark.asyncio
async def test_context_set_refused_without_permission(tmp_path, monkeypatch):
    monkeypatch.setattr("architect.storage.guild_context.DATA_DIR", tmp_path / "data")
    bot = MagicMock()
    cog = ContextCommand(bot)
    interaction = make_interaction(has_manage_guild=False)

    await cog.context_set.callback(cog, interaction)

    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    interaction.response.send_modal.assert_not_called()


@pytest.mark.asyncio
async def test_context_show_with_existing_context(tmp_path, monkeypatch):
    monkeypatch.setattr("architect.storage.guild_context.DATA_DIR", tmp_path / "data")
    from architect.storage.guild_context import save
    save(GuildContext(guild_id=42, name="CS2", objectives="Tournois", tone="Formel", rules=""))
    bot = MagicMock()
    cog = ContextCommand(bot)
    interaction = make_interaction(guild_id=42)

    await cog.context_show.callback(cog, interaction)

    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    embed = kwargs.get("embed")
    assert embed is not None
    field_values = [f.value for f in embed.fields]
    assert any("CS2" in v for v in field_values)


@pytest.mark.asyncio
async def test_context_show_without_context(tmp_path, monkeypatch):
    monkeypatch.setattr("architect.storage.guild_context.DATA_DIR", tmp_path / "data")
    bot = MagicMock()
    cog = ContextCommand(bot)
    interaction = make_interaction(guild_id=99)

    await cog.context_show.callback(cog, interaction)

    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    content = str(args[0]) if args else str(kwargs.get("content", ""))
    assert "/context set" in content or "set" in content.lower()
