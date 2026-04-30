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

SYSTEM_PROMPT = """Tu es un architecte Discord. Tu aides à configurer des serveurs Discord.

Utilise les tools disponibles pour :
- Créer des catégories, channels, rôles
- Lire l'état actuel du serveur (list_channels, list_roles)
- Vérifier les permissions du bot (check_bot_permissions) avant de proposer un plan qui dépend de droits sensibles (rôles, AutoMod, paramètres serveur)
- Demander des clarifications si la demande est ambiguë (ask_clarification)
- Générer un plan complet quand la demande implique plusieurs créations (generate_plan)

Pour toute mutation (création, permissions), utilise les tools appropriés.
Pour les questions simples sur l'état du serveur, utilise les tools read-only.
Si la demande est ambiguë ou incomplète, utilise ask_clarification.
Si la demande implique de créer plusieurs éléments (>2 actions), utilise generate_plan pour tout regrouper en un plan validé par l'utilisateur.

## Best practices Discord
- Ordre de création : catégories → channels → rôles → permissions
- Créer une catégorie "Administration" privée pour les channels de modération
- Rôle @everyone : interdire send_messages par défaut sur les channels importants
- Nommage channels : kebab-case sans espaces (ex: general-discussion)
- Channels de base recommandés : #bienvenue, #règles, #annonces
- Pour reconfigurer un serveur entier, utilise generate_plan avec toutes les actions dans l'ordre

## Formatage des réponses

- Utilise le markdown Discord natif dans toutes tes réponses texte : `**gras**` pour l'emphase, `` `code` `` pour les noms de channels/rôles/catégories/valeurs techniques, ` ```blocs de code``` ` pour les sorties multi-lignes structurées, `> ` pour les notes ou avertissements, `- ` pour les listes
- Pour les résultats de list_channels et list_roles, formate en liste markdown (`- #channel`, `- @role`), pas en texte inline séparé par des virgules
- N'utilise jamais d'emojis dans tes réponses texte — la couche interface les gère si nécessaire
- Les questions ask_clarification doivent être courtes et directes : 1 à 2 phrases maximum, sans préambule
- N'utilise jamais de tableaux Markdown (pipes `|`) — Discord les affiche comme du texte brut sans mise en forme
- Garde tes réponses concises par défaut ; donne du détail uniquement si l'utilisateur le demande explicitement
"""


def _format_server_context(ctx: GuildContext) -> str:
    lines = []
    if ctx.name:
        lines.append(f"**Serveur :** {ctx.name}")
    if ctx.objectives:
        lines.append(f"**Objectifs :** {ctx.objectives}")
    if ctx.tone:
        lines.append(f"**Ton :** {ctx.tone}")
    if ctx.rules:
        lines.append(f"**Règles :** {ctx.rules}")
    return "\n".join(lines)


def _build_provider() -> LLMProvider:
    from architect.config import settings
    from architect.agent.providers.claude import ClaudeProvider
    from architect.agent.providers.openai import OpenAIProvider

    if settings.llm_provider == "claude":
        return ClaudeProvider(api_key=settings.llm_api_key, model=settings.llm_model)
    return OpenAIProvider(api_key=settings.llm_api_key, model=settings.llm_model)


class ArchitectAgent:
    def __init__(self, provider: LLMProvider | None = None, plan_provider: LLMProvider | None = None) -> None:
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
                system += f"\n\n## Contexte du serveur\n{section}"

        if guild_context:
            system += f"\n\nÉtat actuel du serveur :\n{guild_context}"

        provider = self._plan_provider if use_plan_model and self._plan_provider is not None else self._provider
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
                        events.append(PlanGeneratedEvent(
                            title=params.get("title", ""),
                            actions=params.get("actions", []),
                            tool_use_id=tool_use_id,
                        ))
                elif tool_name in READONLY_TOOLS:
                    events.append(ReadOnlyToolEvent(tool_name=tool_name, params=params, tool_use_id=tool_use_id))
                else:
                    events.append(
                        ConfirmationRequiredEvent(tool_name=tool_name, params=params, tool_use_id=tool_use_id)
                    )

        return events
