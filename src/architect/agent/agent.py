import json

from ..config import settings
from ..models.actions import ActionType
from ..models.plan import Plan
from .providers.base import LLMProvider
from .providers.claude import ClaudeProvider
from .providers.openai import OpenAIProvider

# Derived from enum — automatically stays in sync when new ActionTypes are added.
_VALID_TYPES = ", ".join(f'"{t.value}"' for t in ActionType)

# Concrete example: one instance per ActionType. The LLM copies structure, not schema metadata.
_PLAN_EXAMPLE = json.dumps(
    {
        "title": "Example Server",
        "description": "Brief description of what this plan creates.",
        "actions": [
            {"type": "create_category", "params": {"name": "General"}},
            {"type": "create_text_channel", "params": {"name": "welcome", "category": "General"}},
            {"type": "create_voice_channel", "params": {"name": "Lounge", "category": "General"}},
            {"type": "create_role", "params": {"name": "Member", "color": "#3498DB", "mentionable": True}},
            {
                "type": "set_channel_permissions",
                "params": {
                    "channel": "welcome",
                    "role": "Member",
                    "allow": ["read_messages"],
                    "deny": ["send_messages"],
                },
            },
            {"type": "reply", "params": {"message": "Here are the current channels: #general, #welcome"}},
        ],
    },
    indent=2,
)

SYSTEM_PROMPT = (
    "You are a Discord server architect.\n\n"
    "Reply ONLY with a JSON object that has exactly these three keys:\n"
    '  "title"       — a short string name for the plan\n'
    '  "description" — a one-sentence summary\n'
    '  "actions"     — an array of action objects\n\n'
    "Each action object must have exactly two keys:\n"
    f'  "type"   — one of: {_VALID_TYPES}\n'
    '  "params" — an object whose keys depend on the action type\n\n'
    'For read-only requests (listing channels, roles, etc.), use the "reply" action type with '
    'params: {"message": "..."}. Use the server state provided in the user message to populate the reply.\n\n'
    f"Example (follow this structure exactly, no extra keys, no markdown):\n{_PLAN_EXAMPLE}\n\n"
    "Reply ONLY with valid JSON. No markdown fences. No explanation. No schema keys."
)


def _build_provider() -> LLMProvider:
    if settings.llm_provider == "claude":
        return ClaudeProvider(settings.llm_api_key, settings.llm_model)
    if settings.llm_provider == "openai":
        return OpenAIProvider(settings.llm_api_key, settings.llm_model)
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider!r}")


class ArchitectAgent:
    def __init__(self) -> None:
        self._provider = _build_provider()

    async def generate_plan(self, prompt: str, guild_context: str = "") -> Plan:
        user_prompt = prompt
        if guild_context:
            user_prompt = f"{prompt}\n\nCurrent server state:\n{guild_context}"
        raw = await self._provider.complete(SYSTEM_PROMPT, user_prompt)
        return Plan.model_validate_json(raw)
