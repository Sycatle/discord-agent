import pytest
from architect.agent.agent import ArchitectAgent, SYSTEM_PROMPT
from architect.agent.events import (
    ClarificationEvent,
    ConfirmationRequiredEvent,
    ReadOnlyToolEvent,
    ReplyEvent,
)
from architect.agent.providers.base import LLMProvider


class MockProvider(LLMProvider):
    def __init__(self, blocks: list[dict]) -> None:
        self._blocks = blocks
        self.last_system_prompt: str = ""

    async def call_with_tools(self, system_prompt: str, messages: list[dict], tools: list[dict]) -> list[dict]:
        self.last_system_prompt = system_prompt
        return self._blocks


MESSAGES = [{"role": "user", "content": "Hello"}]


@pytest.mark.asyncio
async def test_text_block_produces_reply_event():
    provider = MockProvider([{"type": "text", "text": "Hello"}])
    agent = ArchitectAgent(provider=provider)
    events = await agent.step(MESSAGES)
    assert events == [ReplyEvent(text="Hello")]


@pytest.mark.asyncio
async def test_mutation_tool_produces_confirmation_event():
    provider = MockProvider(
        [{"type": "tool_use", "id": "1", "name": "create_category", "input": {"name": "Gaming"}}]
    )
    agent = ArchitectAgent(provider=provider)
    events = await agent.step(MESSAGES)
    assert events == [
        ConfirmationRequiredEvent(tool_name="create_category", params={"name": "Gaming"}, tool_use_id="1")
    ]


@pytest.mark.asyncio
async def test_readonly_tool_produces_readonly_event():
    provider = MockProvider([{"type": "tool_use", "id": "2", "name": "list_channels", "input": {}}])
    agent = ArchitectAgent(provider=provider)
    events = await agent.step(MESSAGES)
    assert events == [ReadOnlyToolEvent(tool_name="list_channels", params={}, tool_use_id="2")]


@pytest.mark.asyncio
async def test_ask_clarification_tool_produces_clarification_event():
    provider = MockProvider(
        [{"type": "tool_use", "id": "3", "name": "ask_clarification", "input": {"question": "Quel canal ?"}}]
    )
    agent = ArchitectAgent(provider=provider)
    events = await agent.step(MESSAGES)
    assert events == [ClarificationEvent(question="Quel canal ?")]


@pytest.mark.asyncio
async def test_multiple_blocks_returns_events_in_order():
    provider = MockProvider(
        [
            {"type": "text", "text": "Je vais créer le canal."},
            {"type": "tool_use", "id": "10", "name": "create_text_channel", "input": {"name": "general"}},
            {"type": "tool_use", "id": "11", "name": "list_roles", "input": {}},
        ]
    )
    agent = ArchitectAgent(provider=provider)
    events = await agent.step(MESSAGES)
    assert events == [
        ReplyEvent(text="Je vais créer le canal."),
        ConfirmationRequiredEvent(tool_name="create_text_channel", params={"name": "general"}, tool_use_id="10"),
        ReadOnlyToolEvent(tool_name="list_roles", params={}, tool_use_id="11"),
    ]


@pytest.mark.asyncio
async def test_empty_text_block_does_not_produce_event():
    provider = MockProvider([{"type": "text", "text": "   "}])
    agent = ArchitectAgent(provider=provider)
    events = await agent.step(MESSAGES)
    assert events == []


@pytest.mark.asyncio
async def test_guild_context_injected_into_system_prompt():
    provider = MockProvider([])
    agent = ArchitectAgent(provider=provider)
    await agent.step(MESSAGES, guild_context="Channels: #general, #random")
    assert "Channels: #general, #random" in provider.last_system_prompt
    assert provider.last_system_prompt.startswith(SYSTEM_PROMPT)


@pytest.mark.asyncio
async def test_no_guild_context_uses_base_system_prompt():
    provider = MockProvider([])
    agent = ArchitectAgent(provider=provider)
    await agent.step(MESSAGES)
    assert provider.last_system_prompt == SYSTEM_PROMPT
