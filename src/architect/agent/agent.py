import json

from ..config import settings
from ..models.plan import Plan
from .providers.base import LLMProvider
from .providers.claude import ClaudeProvider
from .providers.openai import OpenAIProvider

SYSTEM_PROMPT_TEMPLATE = """\
Tu es un architecte de serveur Discord. Génère un plan structuré en JSON strict \
selon ce schéma exactement :
{schema}
Réponds UNIQUEMENT avec le JSON valide, sans balises markdown, sans explication."""


def _build_provider() -> LLMProvider:
    if settings.llm_provider == "claude":
        return ClaudeProvider(settings.llm_api_key, settings.llm_model)
    if settings.llm_provider == "openai":
        return OpenAIProvider(settings.llm_api_key, settings.llm_model)
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider!r}")


class ArchitectAgent:
    def __init__(self) -> None:
        self._provider = _build_provider()
        self._schema = json.dumps(Plan.model_json_schema(), indent=2)

    async def generate_plan(self, prompt: str) -> Plan:
        system = SYSTEM_PROMPT_TEMPLATE.format(schema=self._schema)
        raw = await self._provider.complete(system, prompt)
        return Plan.model_validate_json(raw)
