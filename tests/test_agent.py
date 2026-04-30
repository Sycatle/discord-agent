import pytest

from architect.agent.agent import SYSTEM_PROMPT, ArchitectAgent
from architect.agent.events import (
    ClarificationEvent,
    ConfirmationRequiredEvent,
    PlanGeneratedEvent,
    ReadOnlyToolEvent,
    ReplyEvent,
)
from architect.agent.providers.base import LLMProvider
from architect.storage.guild_context import GuildContext


class MockProvider(LLMProvider):
    def __init__(self, blocks: list[dict]) -> None:
        self._blocks = blocks
        self.last_system_prompt: str = ""

    async def call_with_tools(
        self, system_prompt: str, messages: list[dict], tools: list[dict]
    ) -> list[dict]:
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
        ConfirmationRequiredEvent(
            tool_name="create_category", params={"name": "Gaming"}, tool_use_id="1"
        )
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
        [
            {
                "type": "tool_use",
                "id": "3",
                "name": "ask_clarification",
                "input": {"question": "Quel canal ?"},
            }
        ]
    )
    agent = ArchitectAgent(provider=provider)
    events = await agent.step(MESSAGES)
    assert events == [ClarificationEvent(question="Quel canal ?")]


@pytest.mark.asyncio
async def test_multiple_blocks_returns_events_in_order():
    provider = MockProvider(
        [
            {"type": "text", "text": "I will create the channel."},
            {
                "type": "tool_use",
                "id": "10",
                "name": "create_text_channel",
                "input": {"name": "general"},
            },
            {"type": "tool_use", "id": "11", "name": "list_roles", "input": {}},
        ]
    )
    agent = ArchitectAgent(provider=provider)
    events = await agent.step(MESSAGES)
    # Text preamble is skipped when tool calls follow to prevent bot layer from stopping
    assert events == [
        ConfirmationRequiredEvent(
            tool_name="create_text_channel", params={"name": "general"}, tool_use_id="10"
        ),
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


@pytest.mark.asyncio
async def test_generate_plan_tool_produces_plan_generated_event():
    provider = MockProvider(
        [
            {
                "type": "tool_use",
                "id": "p1",
                "name": "generate_plan",
                "input": {
                    "title": "Serveur Gaming",
                    "actions": [
                        {"type": "create_category", "params": {"name": "General"}},
                        {
                            "type": "create_text_channel",
                            "params": {"name": "welcome", "category": "General"},
                        },
                    ],
                },
            }
        ]
    )
    agent = ArchitectAgent(provider=provider)
    events = await agent.step(MESSAGES)
    assert len(events) == 1
    evt = events[0]
    assert isinstance(evt, PlanGeneratedEvent)
    assert evt.title == "Serveur Gaming"
    assert len(evt.actions) == 2
    assert evt.tool_use_id == "p1"


@pytest.mark.asyncio
async def test_use_plan_model_uses_plan_provider():
    main_provider = MockProvider([{"type": "text", "text": "chat"}])
    plan_provider = MockProvider([{"type": "text", "text": "plan"}])
    agent = ArchitectAgent(provider=main_provider, plan_provider=plan_provider)

    events = await agent.step(MESSAGES, use_plan_model=False)
    assert events == [ReplyEvent(text="chat")]

    events = await agent.step(MESSAGES, use_plan_model=True)
    assert events == [ReplyEvent(text="plan")]


@pytest.mark.asyncio
async def test_use_plan_model_without_plan_provider_falls_back():
    provider = MockProvider([{"type": "text", "text": "fallback"}])
    agent = ArchitectAgent(provider=provider, plan_provider=None)
    events = await agent.step(MESSAGES, use_plan_model=True)
    assert events == [ReplyEvent(text="fallback")]


def test_system_prompt_contains_best_practices():
    assert "Discord best practices" in SYSTEM_PROMPT
    assert "generate_plan" in SYSTEM_PROMPT
    assert "kebab-case" in SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_server_context_injected_before_guild_context():
    provider = MockProvider([])
    agent = ArchitectAgent(provider=provider)
    ctx = GuildContext(guild_id=1, name="CS2", objectives="Tournois", tone="Formel", rules="Max 10")
    await agent.step(MESSAGES, guild_context="Channels: #general", server_context=ctx)
    prompt = provider.last_system_prompt
    assert "## Server context" in prompt
    assert "**Server:** CS2" in prompt
    assert "**Goals:** Tournois" in prompt
    assert "**Tone:** Formel" in prompt
    assert "**Rules:** Max 10" in prompt
    # server context appears before guild state
    assert prompt.index("## Server context") < prompt.index("Channels: #general")


@pytest.mark.asyncio
async def test_server_context_none_no_section_added():
    provider = MockProvider([])
    agent = ArchitectAgent(provider=provider)
    await agent.step(MESSAGES, server_context=None)
    assert "## Server context" not in provider.last_system_prompt


@pytest.mark.asyncio
async def test_server_context_all_empty_fields_no_section():
    provider = MockProvider([])
    agent = ArchitectAgent(provider=provider)
    ctx = GuildContext(guild_id=1)  # all fields default to ""
    await agent.step(MESSAGES, server_context=ctx)
    assert "## Server context" not in provider.last_system_prompt


@pytest.mark.asyncio
async def test_server_context_partial_fields_only_nonempty_shown():
    provider = MockProvider([])
    agent = ArchitectAgent(provider=provider)
    ctx = GuildContext(guild_id=1, name="My Server")  # only name set
    await agent.step(MESSAGES, server_context=ctx)
    prompt = provider.last_system_prompt
    assert "**Server:** My Server" in prompt
    assert "**Goals:**" not in prompt
    assert "**Tone:**" not in prompt
    assert "**Rules:**" not in prompt
