import pytest

from architect.bot.history import ConversationHistory


@pytest.fixture(autouse=True)
def _isolate_history(tmp_path, monkeypatch):
    """Redirect history persistence to a per-test tmp dir.

    Without this, the default ``settings.data_dir / "history"`` would be
    shared across tests AND with whatever is sitting in the dev `data/`
    directory — making channel-id collisions and stale state inevitable.
    """
    from architect.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)


def test_append_adds_message():
    h = ConversationHistory()
    h.append(1, "user", "hello")
    assert h.get(1) == [{"role": "user", "content": "hello"}]


def test_get_unknown_channel_returns_empty():
    h = ConversationHistory()
    assert h.get(999) == []


def test_get_preserves_order():
    h = ConversationHistory()
    h.append(1, "user", "first")
    h.append(1, "assistant", "second")
    h.append(1, "user", "third")
    msgs = h.get(1)
    assert [m["content"] for m in msgs] == ["first", "second", "third"]


def test_trim_removes_oldest():
    h = ConversationHistory(max_messages=3)
    for i in range(5):
        h.append(1, "user", str(i))
    msgs = h.get(1)
    assert len(msgs) == 3
    assert [m["content"] for m in msgs] == ["2", "3", "4"]


def test_append_tool_result_format():
    h = ConversationHistory()
    h.append_tool_result(1, "tool-id-123", "done")
    msgs = h.get(1)
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == [
        {"type": "tool_result", "tool_use_id": "tool-id-123", "content": "done"}
    ]


def test_append_assistant_tool_calls_format():
    h = ConversationHistory()
    blocks = [
        {"type": "tool_use", "id": "abc", "name": "create_category", "input": {"name": "Gaming"}}
    ]
    h.append_assistant_tool_calls(1, blocks)
    msgs = h.get(1)
    assert len(msgs) == 1
    assert msgs[0]["role"] == "assistant"
    assert msgs[0]["content"] == blocks


def test_clear_removes_channel_history():
    h = ConversationHistory()
    h.append(1, "user", "hello")
    h.clear(1)
    assert h.get(1) == []


def test_clear_nonexistent_channel_does_not_raise():
    h = ConversationHistory()
    h.clear(999)  # should not raise


def test_compact_tool_pair_collapses_use_and_result():
    h = ConversationHistory()
    h.append(1, "user", "wipe everything")
    h.append_assistant_tool_calls(
        1,
        [
            {
                "type": "tool_use",
                "id": "plan-1",
                "name": "generate_plan",
                "input": {"title": "Wipe", "actions": [{"type": "delete_category"}]},
            }
        ],
    )
    h.append_tool_result(1, "plan-1", "1/1 actions executed.")

    replaced = h.compact_tool_pair(1, "plan-1", "Plan exécuté: 1/1 ok")
    assert replaced is True

    msgs = h.get(1)
    # Original user msg + 1 compacted assistant message.
    assert len(msgs) == 2
    assert msgs[0] == {"role": "user", "content": "wipe everything"}
    assert msgs[1] == {"role": "assistant", "content": "Plan exécuté: 1/1 ok"}


def test_compact_tool_pair_unknown_id_returns_false():
    h = ConversationHistory()
    h.append(1, "user", "hi")
    assert h.compact_tool_pair(1, "missing", "summary") is False
    assert h.get(1) == [{"role": "user", "content": "hi"}]


def test_compact_tool_pair_preserves_unrelated_blocks():
    h = ConversationHistory()
    h.append(1, "user", "hi")
    h.append_assistant_tool_calls(
        1,
        [
            {"type": "tool_use", "id": "plan-A", "name": "generate_plan", "input": {}},
        ],
    )
    h.append_tool_result(1, "plan-A", "ok")
    h.append(1, "assistant", "anything else?")

    h.compact_tool_pair(1, "plan-A", "Plan A done")

    msgs = h.get(1)
    assert [m["role"] for m in msgs] == ["user", "assistant", "assistant"]
    assert msgs[1]["content"] == "Plan A done"
    assert msgs[2]["content"] == "anything else?"


def test_channels_are_independent():
    h = ConversationHistory()
    h.append(1, "user", "channel 1")
    h.append(2, "user", "channel 2")
    assert h.get(1) == [{"role": "user", "content": "channel 1"}]
    assert h.get(2) == [{"role": "user", "content": "channel 2"}]
    h.clear(1)
    assert h.get(1) == []
    assert h.get(2) == [{"role": "user", "content": "channel 2"}]


# ---------------------------------------------------------------------------
# Persistence — JSON file per channel survives bot restart
# ---------------------------------------------------------------------------


def test_append_persists_to_disk(tmp_path):
    h = ConversationHistory(data_dir=tmp_path / "history")
    h.append(42, "user", "hello")
    f = tmp_path / "history" / "42.json"
    assert f.exists()
    import json as _json

    payload = _json.loads(f.read_text(encoding="utf-8"))
    assert payload["messages"] == [{"role": "user", "content": "hello"}]


def test_restart_reloads_history_from_disk(tmp_path):
    """Instantiating a new ConversationHistory must rehydrate from JSON."""
    h1 = ConversationHistory(data_dir=tmp_path / "history")
    h1.append(42, "user", "first")
    h1.append(42, "assistant", "second")

    h2 = ConversationHistory(data_dir=tmp_path / "history")
    assert h2.get(42) == [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
    ]


def test_clear_deletes_persisted_file(tmp_path):
    h = ConversationHistory(data_dir=tmp_path / "history")
    h.append(42, "user", "x")
    f = tmp_path / "history" / "42.json"
    assert f.exists()
    h.clear(42)
    assert not f.exists()


def test_compact_tool_pair_is_persisted(tmp_path):
    h = ConversationHistory(data_dir=tmp_path / "history")
    h.append_assistant_tool_calls(
        1, [{"type": "tool_use", "id": "p1", "name": "x", "input": {}}]
    )
    h.append_tool_result(1, "p1", "ok")
    h.compact_tool_pair(1, "p1", "summary")
    h2 = ConversationHistory(data_dir=tmp_path / "history")
    msgs = h2.get(1)
    assert msgs == [{"role": "assistant", "content": "summary"}]


def test_corrupted_file_is_skipped_not_fatal(tmp_path):
    hdir = tmp_path / "history"
    hdir.mkdir()
    (hdir / "1.json").write_text("{not valid")
    (hdir / "2.json").write_text('{"messages": [{"role": "user", "content": "ok"}]}')
    h = ConversationHistory(data_dir=hdir)
    assert h.get(1) == []  # silently skipped
    assert h.get(2) == [{"role": "user", "content": "ok"}]


def test_rolling_window_after_reload(tmp_path):
    h = ConversationHistory(max_messages=3, data_dir=tmp_path / "history")
    for i in range(5):
        h.append(1, "user", str(i))
    h2 = ConversationHistory(max_messages=3, data_dir=tmp_path / "history")
    # The reload reads whatever was persisted (last 3 after trim).
    msgs = h2.get(1)
    assert [m["content"] for m in msgs] == ["2", "3", "4"]
