"""Coverage for the OpenAI ↔ Anthropic message/tool translation.

We don't hit the real OpenAI API. Instead we mock the AsyncOpenAI client's
``chat.completions.create`` so the test exercises the pure translation
layers (``_convert_messages``, ``_convert_tools``, response unpacking).
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from architect.agent.providers.openai import (
    OpenAIProvider,
    _convert_messages,
    _convert_tools,
)


def _ai_response(
    content: str | None = None, tool_calls: list[dict] | None = None
) -> SimpleNamespace:
    """Build a fake ``ChatCompletion`` response shaped like the real SDK."""
    msg = SimpleNamespace(content=content, tool_calls=None)
    if tool_calls:
        msg.tool_calls = [
            SimpleNamespace(
                id=tc["id"],
                function=SimpleNamespace(name=tc["name"], arguments=tc["arguments"]),
            )
            for tc in tool_calls
        ]
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


# ── _convert_messages ───────────────────────────────────────────────────────


def test_convert_messages_plain_string_user_message():
    result = _convert_messages([{"role": "user", "content": "hello"}])
    assert result == [{"role": "user", "content": "hello"}]


def test_convert_messages_assistant_text_block():
    result = _convert_messages([{"role": "assistant", "content": [{"type": "text", "text": "hi"}]}])
    assert result in (
        [{"role": "assistant", "content": "hi", "tool_calls": []}],
        [{"role": "assistant", "content": "hi"}],
    )


def test_convert_messages_assistant_tool_use_block():
    blocks = [
        {"type": "tool_use", "id": "abc", "name": "create_role", "input": {"name": "Mod"}},
    ]
    result = _convert_messages([{"role": "assistant", "content": blocks}])
    assert result[0]["role"] == "assistant"
    assert result[0]["content"] is None
    assert result[0]["tool_calls"][0] == {
        "id": "abc",
        "type": "function",
        "function": {"name": "create_role", "arguments": json.dumps({"name": "Mod"})},
    }


def test_convert_messages_user_tool_result_block():
    blocks = [{"type": "tool_result", "tool_use_id": "abc", "content": "done"}]
    result = _convert_messages([{"role": "user", "content": blocks}])
    assert result == [{"role": "tool", "tool_call_id": "abc", "content": "done"}]


def test_convert_messages_user_text_block_fallback():
    blocks = [{"type": "text", "text": "plain"}]
    result = _convert_messages([{"role": "user", "content": blocks}])
    assert result == [{"role": "user", "content": "plain"}]


def test_convert_messages_unsupported_role_raises():
    with pytest.raises(ValueError, match="Unsupported message role"):
        _convert_messages([{"role": "system", "content": [{"type": "text", "text": "x"}]}])


# ── _convert_tools ──────────────────────────────────────────────────────────


def test_convert_tools_wraps_anthropic_format():
    tools = [
        {
            "name": "create_role",
            "description": "Create a role",
            "input_schema": {"type": "object", "properties": {}},
        }
    ]
    result = _convert_tools(tools)
    assert result == [
        {
            "type": "function",
            "function": {
                "name": "create_role",
                "description": "Create a role",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]


def test_convert_tools_missing_description_defaults_to_empty():
    result = _convert_tools([{"name": "x", "input_schema": {"type": "object", "properties": {}}}])
    assert result[0]["function"]["description"] == ""


# ── OpenAIProvider.call_with_tools ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_with_tools_returns_text_block():
    provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
    fake = _ai_response(content="hello", tool_calls=None)
    with patch.object(
        provider._client.chat.completions, "create", new=AsyncMock(return_value=fake)
    ):
        blocks = await provider.call_with_tools("sys", [{"role": "user", "content": "hi"}], [])
    assert blocks == [{"type": "text", "text": "hello"}]


@pytest.mark.asyncio
async def test_call_with_tools_returns_tool_use_block():
    provider = OpenAIProvider(api_key="sk-test")
    fake = _ai_response(
        content=None,
        tool_calls=[{"id": "id-1", "name": "create_role", "arguments": '{"name": "Mod"}'}],
    )
    with patch.object(
        provider._client.chat.completions, "create", new=AsyncMock(return_value=fake)
    ):
        blocks = await provider.call_with_tools("sys", [], [])
    assert blocks == [
        {"type": "tool_use", "id": "id-1", "name": "create_role", "input": {"name": "Mod"}}
    ]


@pytest.mark.asyncio
async def test_call_with_tools_returns_text_and_tool_use():
    provider = OpenAIProvider(api_key="sk-test")
    fake = _ai_response(
        content="creating",
        tool_calls=[{"id": "x", "name": "create_role", "arguments": "{}"}],
    )
    with patch.object(
        provider._client.chat.completions, "create", new=AsyncMock(return_value=fake)
    ):
        blocks = await provider.call_with_tools("sys", [], [])
    assert blocks[0]["type"] == "text"
    assert blocks[1]["type"] == "tool_use"


@pytest.mark.asyncio
async def test_call_with_tools_malformed_arguments_raises_value_error():
    provider = OpenAIProvider(api_key="sk-test")
    fake = _ai_response(
        content=None,
        tool_calls=[{"id": "x", "name": "create_role", "arguments": "{not json}"}],
    )
    with (
        patch.object(provider._client.chat.completions, "create", new=AsyncMock(return_value=fake)),
        pytest.raises(ValueError, match="malformed tool arguments"),
    ):
        await provider.call_with_tools("sys", [], [])
