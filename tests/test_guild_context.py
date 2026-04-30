import json

from architect.storage.guild_context import GuildContext, load, save


def test_save_creates_data_directory(tmp_path, monkeypatch):
    monkeypatch.setattr("architect.storage.guild_context.DATA_DIR", tmp_path / "data")
    ctx = GuildContext(guild_id=42, name="Test", objectives="Obj", tone="Formel", rules="No spam")
    save(ctx)
    assert (tmp_path / "data" / "42.json").exists()


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("architect.storage.guild_context.DATA_DIR", tmp_path / "data")
    ctx = GuildContext(
        guild_id=42, name="CS2", objectives="Tournois", tone="Formel", rules="Max 10"
    )
    save(ctx)
    loaded = load(42)
    assert loaded is not None
    assert loaded.guild_id == 42
    assert loaded.name == "CS2"
    assert loaded.objectives == "Tournois"
    assert loaded.tone == "Formel"
    assert loaded.rules == "Max 10"


def test_load_returns_none_if_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("architect.storage.guild_context.DATA_DIR", tmp_path / "data")
    result = load(999)
    assert result is None


def test_load_returns_none_if_json_corrupted(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.setattr("architect.storage.guild_context.DATA_DIR", data_dir)
    (data_dir / "42.json").write_text("not valid json {{{")
    result = load(42)
    assert result is None


def test_load_returns_none_if_extra_fields(tmp_path, monkeypatch):
    """extra='forbid' — unknown fields in JSON should fail validation → return None."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.setattr("architect.storage.guild_context.DATA_DIR", data_dir)
    bad = {"guild_id": 42, "name": "X", "objectives": "", "tone": "", "rules": "", "unknown": "bad"}
    (data_dir / "42.json").write_text(json.dumps(bad))
    result = load(42)
    assert result is None


def test_empty_fields_default_to_empty_string():
    ctx = GuildContext(guild_id=1)
    assert ctx.name == ""
    assert ctx.objectives == ""
    assert ctx.tone == ""
    assert ctx.rules == ""
