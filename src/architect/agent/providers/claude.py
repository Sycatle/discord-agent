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
        volatile_suffix: str = "",
    ) -> list[dict]:
        # Cache the tools schema and the stable system prompt: these are the
        # two largest blocks and are stable across turns. The cache breakpoint
        # is placed on the stable system block so the prefix cache covers
        # tools + stable system. The volatile suffix (current server state)
        # is appended as a SEPARATE, NON-cached system block — it changes
        # every turn and would otherwise bust the prefix cache.
        cached_tools = [
            {**t, "cache_control": {"type": "ephemeral"}} if i == len(tools) - 1 else t
            for i, t in enumerate(tools)
        ]
        system_blocks: list[dict] = [
            {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
        ]
        if volatile_suffix:
            system_blocks.append({"type": "text", "text": volatile_suffix})
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system_blocks,
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
