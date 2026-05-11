from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def call_with_tools(
        self,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict],
        volatile_suffix: str = "",
    ) -> list[dict]:
        """
        Call LLM with tool calling. Returns content blocks in Anthropic format:
        - {"type": "text", "text": "..."}
        - {"type": "tool_use", "id": "...", "name": "...", "input": {...}}

        `system_prompt` is the stable instructional preamble, considered safe
        to cache across turns.

        `volatile_suffix` carries content that changes every turn (e.g. the
        current server snapshot). Providers that support prompt caching MUST
        keep this OUT of the cached prefix.
        """
