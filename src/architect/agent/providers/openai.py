import json

from openai import AsyncOpenAI

from .base import LLMProvider

DEFAULT_MODEL = "gpt-4o"


def _convert_messages(messages: list[dict]) -> list[dict]:
    """Convert Anthropic-format messages to OpenAI format."""
    result = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if isinstance(content, str):
            result.append({"role": role, "content": content})
            continue

        # content is a list of blocks
        if role == "assistant":
            text_parts = []
            tool_calls = []
            for block in content:
                if block["type"] == "text":
                    text_parts.append(block["text"])
                elif block["type"] == "tool_use":
                    tool_calls.append(
                        {
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(block["input"]),
                            },
                        }
                    )
            openai_msg: dict = {
                "role": "assistant",
                "content": " ".join(text_parts) if text_parts else None,
            }
            if tool_calls:
                openai_msg["tool_calls"] = tool_calls
            result.append(openai_msg)

        elif role == "user":
            for block in content:
                if block["type"] == "tool_result":
                    result.append(
                        {
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": block.get("content", ""),
                        }
                    )
                else:
                    # fallback: treat as plain text
                    result.append({"role": "user", "content": block.get("text", "")})
        else:
            raise ValueError(f"Unsupported message role for OpenAI conversion: {role!r}")

    return result


def _convert_tools(tools: list[dict]) -> list[dict]:
    """Convert Anthropic-format tools to OpenAI format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "") -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model or DEFAULT_MODEL

    async def call_with_tools(
        self,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict],
    ) -> list[dict]:
        openai_messages = [
            {"role": "system", "content": system_prompt},
            *_convert_messages(messages),
        ]
        openai_tools = _convert_tools(tools)

        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=openai_messages,
            tools=openai_tools,
        )

        msg = resp.choices[0].message
        result = []

        if msg.content:
            result.append({"type": "text", "text": msg.content})

        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    input_data = json.loads(tc.function.arguments)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"OpenAI returned malformed tool arguments for '{tc.function.name}': {e}"
                    ) from e
                result.append(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.function.name,
                        "input": input_data,
                    }
                )

        return result
