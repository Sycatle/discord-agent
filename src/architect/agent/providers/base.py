from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def call_with_tools(
        self,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict],
    ) -> list[dict]:
        """
        Call LLM with tool calling. Returns content blocks in Anthropic format:
        - {"type": "text", "text": "..."}
        - {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
        """
