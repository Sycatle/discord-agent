from __future__ import annotations

from architect.agent.events import (
    AgentEvent,
    ClarificationEvent,
    ConfirmationRequiredEvent,
    PlanGeneratedEvent,
    ReadOnlyToolEvent,
    ReplyEvent,
)
from architect.agent.providers.base import LLMProvider
from architect.agent.tools import META_TOOLS, MUTATION_TOOLS, READONLY_TOOLS, get_tools
from architect.storage.guild_context import GuildContext

_ALL_KNOWN_TOOLS: frozenset[str] = META_TOOLS | READONLY_TOOLS | MUTATION_TOOLS

SYSTEM_PROMPT = """You are a Discord architect. You help configure Discord servers.

Use the available tools to:
- Create categories, channels, roles
- Read the current server state (list_channels, list_roles)
- Check bot permissions (check_bot_permissions) before proposing plans that
  depend on sensitive rights (roles, AutoMod, server settings)
- Ask for clarifications when the request is ambiguous (ask_clarification)
- Generate a complete plan when the request involves several creations
  (generate_plan)

For any mutation (creation, permissions), use the appropriate tools.
For simple questions about the server state, use the read-only tools.
If the request is ambiguous or incomplete, use ask_clarification.
If the request implies creating several items (>2 actions), use generate_plan
to bundle them into a single user-validated plan.

## Discord best practices
- Creation order: categories → channels → roles → permissions
- Create a private "Administration" category for moderation channels
- @everyone role: disallow send_messages by default on important channels
- Channel naming: kebab-case, no spaces (e.g. general-discussion)
- Recommended baseline channels: #welcome, #rules, #announcements
- To reconfigure a whole server, use generate_plan with every action in order

## Response formatting

- Use native Discord markdown in all your text responses: `**bold**` for
  emphasis, `` `code` `` for channel/role/category names and technical
  values, ` ```code blocks``` ` for structured multi-line output, `> ` for
  notes or warnings, `- ` for lists
- For list_channels and list_roles results, format as markdown lists
  (`- #channel`, `- @role`), not inline comma-separated text
- Never use emojis in your text responses — the UI layer handles them
  when needed
- ask_clarification questions must be short and direct: 1 to 2 sentences max,
  no preamble
- Never use Markdown tables (pipes `|`) — Discord renders them as plain text
- Keep responses concise by default; expand only when the user explicitly
  asks for more detail
"""


def _format_server_context(ctx: GuildContext) -> str:
    lines = []
    if ctx.name:
        lines.append(f"**Server:** {ctx.name}")
    if ctx.objectives:
        lines.append(f"**Goals:** {ctx.objectives}")
    if ctx.tone:
        lines.append(f"**Tone:** {ctx.tone}")
    if ctx.rules:
        lines.append(f"**Rules:** {ctx.rules}")
    return "\n".join(lines)


def _build_provider() -> LLMProvider:
    from architect.agent.providers.claude import ClaudeProvider
    from architect.agent.providers.openai import OpenAIProvider
    from architect.config import settings

    if settings.llm_provider == "claude":
        return ClaudeProvider(api_key=settings.llm_api_key, model=settings.llm_model)
    return OpenAIProvider(api_key=settings.llm_api_key, model=settings.llm_model)


class ArchitectAgent:
    def __init__(
        self, provider: LLMProvider | None = None, plan_provider: LLMProvider | None = None
    ) -> None:
        self._provider = provider if provider is not None else _build_provider()
        self._plan_provider = plan_provider

    async def step(
        self,
        messages: list[dict],
        guild_context: str = "",
        server_context: GuildContext | None = None,
        use_plan_model: bool = False,
    ) -> list[AgentEvent]:
        """
        One LLM call. Returns list of AgentEvents for the bot layer to process.
        The multi-turn loop is managed by the bot layer.

        messages: conversation history in Anthropic format
        server_context: structured server context (guild metadata)
        guild_context: current server state string (injected into system prompt)
        """
        system = SYSTEM_PROMPT

        if server_context is not None:
            section = _format_server_context(server_context)
            if section:
                system += f"\n\n## Server context\n{section}"

        if guild_context:
            system += f"\n\nCurrent server state:\n{guild_context}"

        provider = (
            self._plan_provider
            if use_plan_model and self._plan_provider is not None
            else self._provider
        )
        blocks = await provider.call_with_tools(system, messages, get_tools())

        events: list[AgentEvent] = []
        has_tool_use = any(b["type"] == "tool_use" for b in blocks)

        for block in blocks:
            if block["type"] == "text":
                text = block["text"].strip()
                if text and not has_tool_use:  # skip preamble if tool calls follow
                    events.append(ReplyEvent(text=text))
            elif block["type"] == "tool_use":
                tool_name = block["name"]
                params = block["input"]
                tool_use_id = block["id"]
                if tool_name not in _ALL_KNOWN_TOOLS:
                    raise ValueError(f"LLM called unknown tool: {tool_name!r}")
                if tool_name in META_TOOLS:
                    if tool_name == "ask_clarification":
                        events.append(ClarificationEvent(question=params.get("question", "")))
                    elif tool_name == "generate_plan":
                        events.append(
                            PlanGeneratedEvent(
                                title=params.get("title", ""),
                                actions=params.get("actions", []),
                                tool_use_id=tool_use_id,
                            )
                        )
                elif tool_name in READONLY_TOOLS:
                    events.append(
                        ReadOnlyToolEvent(
                            tool_name=tool_name, params=params, tool_use_id=tool_use_id
                        )
                    )
                else:
                    events.append(
                        ConfirmationRequiredEvent(
                            tool_name=tool_name, params=params, tool_use_id=tool_use_id
                        )
                    )

        return events
