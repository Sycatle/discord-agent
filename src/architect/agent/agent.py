from __future__ import annotations

from architect.agent.events import (
    AgentEvent,
    ClarificationEvent,
    ConfirmationRequiredEvent,
    ReadOnlyToolEvent,
    ReplyEvent,
)
from architect.agent.providers.base import LLMProvider
from architect.agent.tools import META_TOOLS, MUTATION_TOOLS, READONLY_TOOLS, get_tools

_ALL_KNOWN_TOOLS: frozenset[str] = META_TOOLS | READONLY_TOOLS | MUTATION_TOOLS

SYSTEM_PROMPT = """Tu es un architecte Discord. Tu aides à configurer des serveurs Discord.

Utilise les tools disponibles pour :
- Créer des catégories, channels, rôles
- Lire l'état actuel du serveur (list_channels, list_roles)
- Demander des clarifications si la demande est ambiguë (ask_clarification)

Pour toute mutation (création, permissions), utilise les tools appropriés.
Pour les questions simples sur l'état du serveur, utilise les tools read-only.
Si la demande est ambiguë ou incomplète, utilise ask_clarification.
"""


def _build_provider() -> LLMProvider:
    from architect.config import settings
    from architect.agent.providers.claude import ClaudeProvider
    from architect.agent.providers.openai import OpenAIProvider

    if settings.llm_provider == "claude":
        return ClaudeProvider(api_key=settings.llm_api_key, model=settings.llm_model)
    return OpenAIProvider(api_key=settings.llm_api_key, model=settings.llm_model)


class ArchitectAgent:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider if provider is not None else _build_provider()

    async def step(self, messages: list[dict], guild_context: str = "") -> list[AgentEvent]:
        """
        One LLM call. Returns list of AgentEvents for the bot layer to process.
        The multi-turn loop is managed by the bot layer.

        messages: conversation history in Anthropic format
        guild_context: current server state string (injected into system prompt)
        """
        system = SYSTEM_PROMPT
        if guild_context:
            system += f"\n\nÉtat actuel du serveur :\n{guild_context}"

        blocks = await self._provider.call_with_tools(system, messages, get_tools())

        events: list[AgentEvent] = []
        for block in blocks:
            if block["type"] == "text":
                text = block["text"].strip()
                if text:
                    events.append(ReplyEvent(text=text))
            elif block["type"] == "tool_use":
                tool_name = block["name"]
                params = block["input"]
                tool_use_id = block["id"]
                if tool_name not in _ALL_KNOWN_TOOLS:
                    raise ValueError(f"LLM called unknown tool: {tool_name!r}")
                if tool_name in META_TOOLS:
                    events.append(ClarificationEvent(question=params.get("question", "")))
                elif tool_name in READONLY_TOOLS:
                    events.append(ReadOnlyToolEvent(tool_name=tool_name, params=params, tool_use_id=tool_use_id))
                else:
                    events.append(
                        ConfirmationRequiredEvent(tool_name=tool_name, params=params, tool_use_id=tool_use_id)
                    )

        return events
