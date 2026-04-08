from openai import AsyncOpenAI
from .base import LLMProvider

DEFAULT_MODEL = "gpt-4o"


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "") -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model or DEFAULT_MODEL

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        resp = await self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content
