from architect.agent.events import (
    AgentEvent,
    ClarificationEvent,
    ConfirmationRequiredEvent,
    ReadOnlyToolEvent,
    ReplyEvent,
    ToolCallEvent,
)


def test_reply_event_instantiation():
    e = ReplyEvent(text="hello")
    assert e.text == "hello"


def test_tool_call_event_instantiation():
    e = ToolCallEvent(tool_name="create_channel", params={"name": "general"}, tool_use_id="abc123")
    assert e.tool_name == "create_channel"
    assert e.params == {"name": "general"}
    assert e.tool_use_id == "abc123"


def test_confirmation_required_event_instantiation():
    e = ConfirmationRequiredEvent(tool_name="create_channel", params={}, tool_use_id="id1")
    assert e.tool_name == "create_channel"
    assert e.tool_use_id == "id1"


def test_readonly_tool_event_instantiation():
    e = ReadOnlyToolEvent(tool_name="list_channels", params={}, tool_use_id="id2")
    assert e.tool_name == "list_channels"
    assert e.tool_use_id == "id2"


def test_clarification_event_instantiation():
    e = ClarificationEvent(question="Which channel?")
    assert e.question == "Which channel?"


def test_confirmation_required_is_tool_call_event():
    e = ConfirmationRequiredEvent(tool_name="t", params={}, tool_use_id="x")
    assert isinstance(e, ToolCallEvent)


def test_readonly_tool_is_tool_call_event():
    e = ReadOnlyToolEvent(tool_name="t", params={}, tool_use_id="x")
    assert isinstance(e, ToolCallEvent)


def test_clarification_event_not_tool_call_event():
    e = ClarificationEvent(question="?")
    assert not isinstance(e, ToolCallEvent)


def test_reply_event_not_tool_call_event():
    e = ReplyEvent(text="hi")
    assert not isinstance(e, ToolCallEvent)


def test_fields_readable():
    reply = ReplyEvent(text="response")
    assert reply.text == "response"

    confirm = ConfirmationRequiredEvent(tool_name="create_role", params={"name": "mod"}, tool_use_id="u1")
    assert confirm.tool_name == "create_role"
    assert confirm.params == {"name": "mod"}
    assert confirm.tool_use_id == "u1"

    ro = ReadOnlyToolEvent(tool_name="list_roles", params={}, tool_use_id="u2")
    assert ro.tool_name == "list_roles"

    clarif = ClarificationEvent(question="what?")
    assert clarif.question == "what?"
