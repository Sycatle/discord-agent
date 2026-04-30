"""Error-path coverage for ``Executor.execute``.

Exercises the four failure modes wrapped by the dispatcher: missing bot
permission, ``discord.Forbidden``, ``discord.NotFound``,
``discord.HTTPException``. Each is tested in both strict and non-strict
modes so the agentic loop and the atomic batch coordinator paths are
both covered.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from architect.executor.executor import ExecuteError, Executor


class _Perms:
    """A flexible stand-in for ``discord.Permissions`` whose missing attributes
    default to ``False`` (just like the real type with no flags set)."""

    def __init__(self, **granted: bool) -> None:
        self.__dict__.update(granted)

    def __getattr__(self, name: str) -> bool:
        return False


def _guild_with_perms(**granted_perms: bool) -> MagicMock:
    """Return a mock guild whose ``guild.me.guild_permissions.<name>`` returns
    the boolean from ``granted_perms``, defaulting to ``False`` for unknown
    permissions."""
    guild = MagicMock()
    me = MagicMock()
    me.guild_permissions = _Perms(**granted_perms)
    guild.me = me
    return guild


def _make_http_exception(status: int, text: str = "rate limited") -> discord.HTTPException:
    """Build a real ``discord.HTTPException`` without a real HTTP roundtrip."""
    response = MagicMock()
    response.status = status
    return discord.HTTPException(response, text)


# ── Permission pre-check ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_missing_permission_returns_string_in_non_strict_mode():
    guild = _guild_with_perms(manage_channels=False)
    result = await Executor().execute("create_category", {"name": "x"}, guild)
    assert "Missing permission" in result
    assert "manage_channels" in result


@pytest.mark.asyncio
async def test_missing_permission_raises_in_strict_mode():
    guild = _guild_with_perms(manage_channels=False)
    with pytest.raises(ExecuteError, match="Missing permission"):
        await Executor().execute("create_category", {"name": "x"}, guild, strict=True)


@pytest.mark.asyncio
async def test_unknown_tool_raises_not_implemented():
    guild = _guild_with_perms()
    with pytest.raises(NotImplementedError, match="No handler"):
        await Executor().execute("nuke_everything", {}, guild)


@pytest.mark.asyncio
async def test_invalid_params_returns_validation_error_string():
    guild = _guild_with_perms(manage_channels=True)
    # name is required for create_category — pass an empty payload.
    result = await Executor().execute("create_category", {}, guild)
    assert "Invalid parameters" in result


@pytest.mark.asyncio
async def test_invalid_params_raises_in_strict_mode():
    guild = _guild_with_perms(manage_channels=True)
    with pytest.raises(ExecuteError, match="Invalid parameters"):
        await Executor().execute("create_category", {}, guild, strict=True)


# ── Discord error wrapping ──────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc_factory", "expected"),
    [
        (lambda: discord.Forbidden(MagicMock(status=403), "no"), "Action refused by Discord"),
        (lambda: discord.NotFound(MagicMock(status=404), "gone"), "Entity not found"),
        (lambda: _make_http_exception(429, "rate limited"), "Discord error"),
    ],
)
async def test_discord_errors_wrapped_in_non_strict_mode(exc_factory, expected):
    guild = _guild_with_perms(manage_channels=True)
    guild.create_category = AsyncMock(side_effect=exc_factory())
    result = await Executor().execute("create_category", {"name": "x"}, guild)
    assert expected in result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc_factory",
    [
        lambda: discord.Forbidden(MagicMock(status=403), "no"),
        lambda: discord.NotFound(MagicMock(status=404), "gone"),
        lambda: _make_http_exception(500, "boom"),
    ],
)
async def test_discord_errors_raise_execute_error_in_strict_mode(exc_factory):
    guild = _guild_with_perms(manage_channels=True)
    guild.create_category = AsyncMock(side_effect=exc_factory())
    with pytest.raises(ExecuteError):
        await Executor().execute("create_category", {"name": "x"}, guild, strict=True)


@pytest.mark.asyncio
async def test_readonly_tool_runs_without_permission_check():
    """Read-only tools have ``required_permission=None`` and shouldn't trip
    the permission gate even when the bot has no permissions."""
    guild = MagicMock()
    guild.me = MagicMock()
    guild.me.guild_permissions = type("Perms", (), {})()  # nothing granted
    guild.categories = []
    guild.text_channels = []
    guild.voice_channels = []
    result = await Executor().execute("list_channels", {}, guild)
    assert "Categories" in result
