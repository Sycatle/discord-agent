class ConversationHistory:
    def __init__(self, max_messages: int = 40) -> None:
        self._store: dict[int, list[dict]] = {}
        self._max = max_messages

    def _get_or_create(self, channel_id: int) -> list[dict]:
        if channel_id not in self._store:
            self._store[channel_id] = []
        return self._store[channel_id]

    def append(self, channel_id: int, role: str, content: str | list) -> None:
        """Append a message to the channel's history. role = 'user' | 'assistant'"""
        messages = self._get_or_create(channel_id)
        messages.append({"role": role, "content": content})
        if len(messages) > self._max:
            del messages[: len(messages) - self._max]

    def append_tool_result(self, channel_id: int, tool_use_id: str, result: str) -> None:
        """Append a tool result to the channel's history.

        In Anthropic format, tool results are user messages with content blocks:
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "...", "content": "..."}]}
        """
        self.append(
            channel_id,
            "user",
            [{"type": "tool_result", "tool_use_id": tool_use_id, "content": result}],
        )

    def append_assistant_tool_calls(self, channel_id: int, tool_calls_blocks: list[dict]) -> None:
        """Append an assistant message containing tool_use blocks.

        In Anthropic format:
        {"role": "assistant", "content": [{"type": "tool_use", "id": "...", "name": "...", "input": {...}}]}
        """
        self.append(channel_id, "assistant", tool_calls_blocks)

    def get(self, channel_id: int) -> list[dict]:
        """Return the message history for a channel (empty list if no history)."""
        return self._store.get(channel_id, [])

    def clear(self, channel_id: int) -> None:
        """Clear the history for a channel."""
        self._store.pop(channel_id, None)
