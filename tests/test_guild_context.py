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
    assert ctx.preferences == []
    assert ctx.recent_decisions == []


def test_record_preference_appends():
    ctx = GuildContext(guild_id=1)
    assert ctx.record("noms en français", kind="preference") is True
    assert ctx.preferences == ["noms en français"]


def test_record_decision_appends_to_decisions_bucket():
    ctx = GuildContext(guild_id=1)
    ctx.record("user refused AutoMod", kind="decision")
    assert ctx.recent_decisions == ["user refused AutoMod"]
    assert ctx.preferences == []


def test_record_duplicates_are_skipped():
    ctx = GuildContext(guild_id=1)
    assert ctx.record("English server", kind="preference") is True
    assert ctx.record("English server", kind="preference") is False
    assert ctx.preferences == ["English server"]


def test_record_empty_is_rejected():
    ctx = GuildContext(guild_id=1)
    assert ctx.record("   ", kind="preference") is False
    assert ctx.preferences == []


def test_record_fifo_cap_at_20():
    ctx = GuildContext(guild_id=1)
    for i in range(25):
        ctx.record(f"pref {i}", kind="preference")
    assert len(ctx.preferences) == 20
    # Oldest 5 should have been evicted, newest 20 retained.
    assert ctx.preferences[0] == "pref 5"
    assert ctx.preferences[-1] == "pref 24"


def test_save_and_load_preserves_preferences(tmp_path, monkeypatch):
    monkeypatch.setattr("architect.storage.guild_context.DATA_DIR", tmp_path / "data")
    ctx = GuildContext(guild_id=42)
    ctx.record("noms en français", kind="preference")
    ctx.record("user refused AutoMod", kind="decision")
    save(ctx)
    loaded = load(42)
    assert loaded is not None
    assert loaded.preferences == ["noms en français"]
    assert loaded.recent_decisions == ["user refused AutoMod"]


def test_record_finding_appends():
    ctx = GuildContext(guild_id=1)
    assert ctx.record_finding("risk", "perms permissives sur @everyone", 4) is True
    assert len(ctx.findings) == 1
    assert ctx.findings[0].summary == "perms permissives sur @everyone"
    assert ctx.findings[0].severity == 4


def test_record_finding_clamps_severity():
    ctx = GuildContext(guild_id=1)
    ctx.record_finding("risk", "x", 99)
    assert ctx.findings[0].severity == 5
    ctx.record_finding("health", "y", -3)
    assert ctx.findings[-1].severity == 1


def test_record_finding_dedup_consecutive():
    ctx = GuildContext(guild_id=1)
    ctx.record_finding("risk", "same", 3)
    assert ctx.record_finding("risk", "same", 3) is False
    assert len(ctx.findings) == 1


def test_record_constraint_dedups_with_move_to_end():
    ctx = GuildContext(guild_id=1)
    ctx.record_constraint("rule A")
    ctx.record_constraint("rule B")
    ctx.record_constraint("rule A")
    assert ctx.learned_constraints == ["rule B", "rule A"]


def test_record_constraint_fifo_cap_30():
    ctx = GuildContext(guild_id=1)
    for i in range(35):
        ctx.record_constraint(f"rule {i}")
    assert len(ctx.learned_constraints) == 30
    assert ctx.learned_constraints[0] == "rule 5"


def test_save_and_load_preserves_findings_and_constraints(tmp_path, monkeypatch):
    monkeypatch.setattr("architect.storage.guild_context.DATA_DIR", tmp_path / "data")
    ctx = GuildContext(guild_id=42)
    ctx.record_finding("opportunity", "create #welcome", 2)
    ctx.record_constraint("pas de role > bot top role")
    save(ctx)
    loaded = load(42)
    assert loaded is not None
    assert len(loaded.findings) == 1
    assert loaded.findings[0].category == "opportunity"
    assert loaded.learned_constraints == ["pas de role > bot top role"]
