"""Pre-execution snapshot persistence."""

from __future__ import annotations

import json
import time

import pytest

from architect.models.snapshot import ChannelInfo, GuildSnapshot
from architect.storage import snapshots


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshots.settings, "data_dir", tmp_path)
    return tmp_path


def _snap() -> GuildSnapshot:
    return GuildSnapshot(
        categories=[ChannelInfo(id=1, name="Cat", type="category", position=0)],
        channels=[
            ChannelInfo(id=2, name="general", type="text", parent_id=1, position=0)
        ],
    )


def test_save_creates_directory_and_file(tmp_data_dir):
    path = snapshots.save_pre_exec_snapshot(
        guild_id=42, snapshot=_snap(), plan_title="Test", plan_actions=[]
    )
    assert path.exists()
    assert path.parent == tmp_data_dir / "snapshots"
    assert path.name.startswith("42_")
    assert path.name.endswith(".json")


def test_save_payload_is_valid_json(tmp_data_dir):
    path = snapshots.save_pre_exec_snapshot(
        guild_id=42,
        snapshot=_snap(),
        plan_title="Compactage",
        plan_actions=[{"type": "create_text_channel", "params": {"name": "x"}}],
    )
    payload = json.loads(path.read_text())
    assert payload["guild_id"] == 42
    assert payload["plan_title"] == "Compactage"
    assert payload["plan_actions"][0]["type"] == "create_text_channel"
    assert payload["snapshot"]["channels"][0]["name"] == "general"
    # ISO-8601 timestamp is present.
    assert "T" in payload["timestamp"]


def test_load_latest_returns_most_recent(tmp_data_dir):
    snapshots.save_pre_exec_snapshot(
        guild_id=42, snapshot=_snap(), plan_title="First", plan_actions=[]
    )
    # Ensure distinct unix timestamps.
    time.sleep(1.05)
    snapshots.save_pre_exec_snapshot(
        guild_id=42, snapshot=_snap(), plan_title="Second", plan_actions=[]
    )
    loaded = snapshots.load_latest_snapshot(42)
    assert loaded is not None
    _, payload = loaded
    assert payload["plan_title"] == "Second"


def test_load_latest_missing_returns_none(tmp_data_dir):
    assert snapshots.load_latest_snapshot(99) is None


def test_prune_keeps_last_n(tmp_data_dir):
    for i in range(7):
        snapshots.save_pre_exec_snapshot(
            guild_id=42, snapshot=_snap(), plan_title=f"p{i}", plan_actions=[]
        )
        time.sleep(1.01)  # filename includes unix ts → must change
    deleted = snapshots.prune_old_snapshots(42, keep_last=3)
    assert deleted == 4
    remaining = snapshots.list_snapshots(42)
    assert len(remaining) == 3


def test_list_snapshots_scoped_by_guild(tmp_data_dir):
    snapshots.save_pre_exec_snapshot(
        guild_id=42, snapshot=_snap(), plan_title="x", plan_actions=[]
    )
    snapshots.save_pre_exec_snapshot(
        guild_id=99, snapshot=_snap(), plan_title="y", plan_actions=[]
    )
    assert len(snapshots.list_snapshots(42)) == 1
    assert len(snapshots.list_snapshots(99)) == 1
    assert snapshots.list_snapshots(1234) == []
