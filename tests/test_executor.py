# tests/test_executor.py
import pytest
from unittest.mock import AsyncMock, MagicMock
import discord

from architect.executor.executor import Executor
from architect.models.actions import Action, ActionType
from architect.models.plan import Plan


def _make_guild() -> MagicMock:
    """Build a minimal mock discord.Guild."""
    guild = MagicMock(spec=discord.Guild)
    guild.categories = []
    guild.roles = []

    cat = MagicMock(); cat.name = "Gaming"
    ch_text = MagicMock(); ch_text.name = "general"; ch_text.set_permissions = AsyncMock()
    ch_voice = MagicMock(); ch_voice.name = "Vocal"
    role = MagicMock(); role.name = "Joueur"

    guild.channels = [ch_text]
    guild.roles = [role]

    guild.create_category = AsyncMock(return_value=cat)
    guild.create_text_channel = AsyncMock(return_value=ch_text)
    guild.create_voice_channel = AsyncMock(return_value=ch_voice)
    guild.create_role = AsyncMock(return_value=role)
    return guild


async def test_execute_create_category():
    guild = _make_guild()
    plan = Plan(
        title="T", description="D",
        actions=[Action(type=ActionType.CREATE_CATEGORY, params={"name": "Gaming"})]
    )
    results = await Executor().execute(plan, guild)
    assert len(results) == 1
    assert "Gaming" in results[0]
    guild.create_category.assert_called_once_with(name="Gaming")


async def test_execute_create_text_channel():
    guild = _make_guild()
    plan = Plan(
        title="T", description="D",
        actions=[Action(type=ActionType.CREATE_TEXT_CHANNEL, params={"name": "general"})]
    )
    results = await Executor().execute(plan, guild)
    assert "general" in results[0]
    guild.create_text_channel.assert_called_once_with(name="general", category=None)


async def test_execute_create_role():
    guild = _make_guild()
    plan = Plan(
        title="T", description="D",
        actions=[Action(type=ActionType.CREATE_ROLE, params={"name": "Joueur"})]
    )
    results = await Executor().execute(plan, guild)
    assert "Joueur" in results[0]
    guild.create_role.assert_called_once()


async def test_execute_multiple_actions_in_order():
    guild = _make_guild()
    plan = Plan(
        title="T", description="D",
        actions=[
            Action(type=ActionType.CREATE_CATEGORY, params={"name": "Gaming"}),
            Action(type=ActionType.CREATE_TEXT_CHANNEL, params={"name": "general"}),
        ]
    )
    results = await Executor().execute(plan, guild)
    assert len(results) == 2
    guild.create_category.assert_called_once()
    guild.create_text_channel.assert_called_once()


async def test_execute_create_voice_channel():
    guild = _make_guild()
    plan = Plan(
        title="T", description="D",
        actions=[Action(type=ActionType.CREATE_VOICE_CHANNEL, params={"name": "Vocal"})]
    )
    results = await Executor().execute(plan, guild)
    assert "Vocal" in results[0]
    guild.create_voice_channel.assert_called_once_with(name="Vocal", category=None)


async def test_execute_set_channel_permissions():
    guild = _make_guild()
    plan = Plan(
        title="T", description="D",
        actions=[Action(
            type=ActionType.SET_CHANNEL_PERMISSIONS,
            params={"channel": "general", "role": "Joueur", "permissions": {"view_channel": True}},
        )]
    )
    results = await Executor().execute(plan, guild)
    assert "general" in results[0]
    assert "Joueur" in results[0]
    # guild.channels[0] is ch_text (name="general"), guild.roles[0] is role (name="Joueur")
    guild.channels[0].set_permissions.assert_called_once()


async def test_execute_reply():
    guild = _make_guild()
    plan = Plan(
        title="T", description="D",
        actions=[Action(type=ActionType.REPLY, params={"message": "Here are the channels: #general"})]
    )
    results = await Executor().execute(plan, guild)
    assert results == ["Here are the channels: #general"]
    guild.create_category.assert_not_called()
    guild.create_text_channel.assert_not_called()
    guild.create_role.assert_not_called()
