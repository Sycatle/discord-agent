import anthropic
from .base import LLMProvider

DEFAULT_MODEL = "claude-sonnet-4-6"


class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "") -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model or DEFAULT_MODEL

    async def call_with_tools(
        self,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict],
    ) -> list[dict]:
        # Cache le system prompt + le tools schema (les deux blocs les plus volumineux
        # et stables d'un tour à l'autre). Le dernier bloc cache_control couvre tout
        # ce qui le précède dans l'ordre canonique tools → system → messages.
        cached_tools = [
            {**t, "cache_control": {"type": "ephemeral"}} if i == len(tools) - 1 else t
            for i, t in enumerate(tools)
        ]
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            tools=cached_tools,
        )
        result = []
        for block in msg.content:
            if block.type == "text":
                result.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                result.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
        return result
