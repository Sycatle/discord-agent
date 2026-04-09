import pytest

from architect.bot.history import ConversationHistory


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
    blocks = [{"type": "tool_use", "id": "abc", "name": "create_category", "input": {"name": "Gaming"}}]
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


def test_channels_are_independent():
    h = ConversationHistory()
    h.append(1, "user", "channel 1")
    h.append(2, "user", "channel 2")
    assert h.get(1) == [{"role": "user", "content": "channel 1"}]
    assert h.get(2) == [{"role": "user", "content": "channel 2"}]
    h.clear(1)
    assert h.get(1) == []
    assert h.get(2) == [{"role": "user", "content": "channel 2"}]
