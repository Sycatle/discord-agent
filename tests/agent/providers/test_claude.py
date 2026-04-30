"""Coverage for the Claude provider.

Mocks ``anthropic.AsyncAnthropic.messages.create`` so the test only
exercises the cache-control wrapping and the response block translation.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from architect.agent.providers.claude import ClaudeProvider


def _make_response(blocks: list[dict]) -> SimpleNamespace:
    resp_blocks = []
    for b in blocks:
        if b["type"] == "text":
            resp_blocks.append(SimpleNamespace(type="text", text=b["text"]))
        elif b["type"] == "tool_use":
            resp_blocks.append(
                SimpleNamespace(type="tool_use", id=b["id"], name=b["name"], input=b["input"])
            )
    return SimpleNamespace(content=resp_blocks)


@pytest.mark.asyncio
async def test_call_with_tools_returns_text_blocks():
    provider = ClaudeProvider(api_key="sk-test", model="claude-test")
    fake = _make_response([{"type": "text", "text": "hi"}])
    with patch.object(provider._client.messages, "create", new=AsyncMock(return_value=fake)):
        blocks = await provider.call_with_tools(
            "sys",
            [{"role": "user", "content": "hello"}],
            [{"name": "t", "description": "", "input_schema": {}}],
        )
    assert blocks == [{"type": "text", "text": "hi"}]


@pytest.mark.asyncio
async def test_call_with_tools_returns_tool_use_blocks():
    provider = ClaudeProvider(api_key="sk-test")
    fake = _make_response([{"type": "tool_use", "id": "a", "name": "x", "input": {"k": "v"}}])
    with patch.object(provider._client.messages, "create", new=AsyncMock(return_value=fake)):
        blocks = await provider.call_with_tools("sys", [], [])
    assert blocks == [{"type": "tool_use", "id": "a", "name": "x", "input": {"k": "v"}}]


@pytest.mark.asyncio
async def test_call_with_tools_caches_last_tool():
    """The provider attaches cache_control to the last tool to maximise hits."""
    provider = ClaudeProvider(api_key="sk-test")
    fake = _make_response([])
    create_mock = AsyncMock(return_value=fake)
    with patch.object(provider._client.messages, "create", new=create_mock):
        await provider.call_with_tools(
            "sys",
            [],
            [
                {"name": "a", "description": "", "input_schema": {}},
                {"name": "b", "description": "", "input_schema": {}},
            ],
        )
    sent_tools = create_mock.call_args.kwargs["tools"]
    assert "cache_control" not in sent_tools[0]
    assert sent_tools[1]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_system_prompt_carries_cache_control():
    provider = ClaudeProvider(api_key="sk-test")
    fake = _make_response([])
    create_mock = AsyncMock(return_value=fake)
    with patch.object(provider._client.messages, "create", new=create_mock):
        await provider.call_with_tools("hello", [], [])
    system_arg = create_mock.call_args.kwargs["system"]
    assert system_arg[0]["text"] == "hello"
    assert system_arg[0]["cache_control"] == {"type": "ephemeral"}
