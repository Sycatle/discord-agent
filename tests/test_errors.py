"""Discord error decoding."""

from __future__ import annotations

from unittest.mock import MagicMock

import discord

from architect.executor.errors import extract_learned_constraint, format_discord_error


def _make_http(code: int = 0, status: int = 0, text: str = "") -> discord.HTTPException:
    """Build a discord.HTTPException with the given Discord code + HTTP status."""
    response = MagicMock()
    response.status = status
    body = {"code": code, "message": text} if code else {"message": text}
    exc = discord.HTTPException(response, body)
    # discord.HTTPException sets `.status`, `.code`, `.text` from the response.
    # The MagicMock may not — patch explicitly for determinism.
    exc.status = status
    exc.code = code
    exc.text = text
    return exc


def test_known_code_50013_uses_lock_emoji():
    exc = _make_http(code=50013, status=403, text="Missing Permissions")
    msg = format_discord_error(exc, "create_text_channel")
    assert "🔒" in msg
    assert "Permissions manquantes" in msg
    assert "create_text_channel" in msg
    assert "code 50013" in msg


def test_known_code_50024_wrong_channel_type():
    exc = _make_http(code=50024, status=400, text="Cannot execute action")
    msg = format_discord_error(exc, "create_thread")
    assert "⚠" in msg
    assert "Type de channel incompatible" in msg


def test_known_code_10003_unknown_channel():
    exc = _make_http(code=10003, status=404, text="Unknown Channel")
    msg = format_discord_error(exc, "edit_channel")
    assert "❓" in msg
    assert "Channel inconnu" in msg


def test_known_code_30013_max_channels():
    exc = _make_http(code=30013, status=400, text="Max number of channels")
    msg = format_discord_error(exc, "create_text_channel")
    assert "📊" in msg
    assert "500 channels" in msg


def test_known_code_30005_max_roles():
    exc = _make_http(code=30005, status=400, text="Max number of roles")
    msg = format_discord_error(exc, "create_role")
    assert "📊" in msg
    assert "250 rôles" in msg


def test_fallback_status_429():
    exc = _make_http(code=0, status=429, text="Too Many Requests")
    msg = format_discord_error(exc, "edit_channel")
    assert "⏳" in msg
    assert "Rate-limited" in msg


def test_fallback_status_500():
    exc = _make_http(code=0, status=500, text="Internal Server Error")
    msg = format_discord_error(exc, "edit_channel")
    assert "🔧" in msg
    assert "indisponible" in msg


def test_fallback_status_403_without_code():
    exc = _make_http(code=0, status=403, text="Forbidden")
    msg = format_discord_error(exc, "delete_channel")
    assert "🔒" in msg
    assert "delete_channel" in msg


def test_fallback_status_404_without_code():
    exc = _make_http(code=0, status=404, text="Not Found")
    msg = format_discord_error(exc, "delete_role")
    assert "❓" in msg


def test_raw_text_appended_when_distinct():
    exc = _make_http(code=50013, status=403, text="Channel `general` blocked")
    msg = format_discord_error(exc, "edit_channel")
    assert "Channel `general` blocked" in msg


def test_raw_text_skipped_when_redundant():
    """If raw text is a substring of the friendly message, don't duplicate."""
    exc = _make_http(code=50013, status=403, text="permissions manquantes")
    msg = format_discord_error(exc, "edit_channel")
    # The friendly message already contains "Permissions manquantes" — raw
    # text is a lowercase variant and must NOT be appended again.
    assert msg.lower().count("permissions manquantes") == 1


def test_extract_learned_constraint_known_code():
    exc = _make_http(code=50013, status=403, text="x")
    constraint = extract_learned_constraint(exc)
    assert constraint is not None
    assert "permissions" in constraint.lower()


def test_extract_learned_constraint_unknown_code():
    exc = _make_http(code=99999, status=400, text="x")
    assert extract_learned_constraint(exc) is None


def test_extract_learned_constraint_no_code():
    exc = _make_http(code=0, status=500, text="oops")
    assert extract_learned_constraint(exc) is None
