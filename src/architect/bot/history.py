"""Conversation history per Discord channel/thread.

The store is in-memory but mirrored to ``{data_dir}/history/{channel_id}.json``
after every mutation so the bot can resume a conversation across restarts.
JSON I/O is synchronous: each file is small (capped at 40 messages, typically
< 10 KB after the plan-compaction pass), so the latency cost is negligible
compared to a single LLM call.

Backwards compatibility: the public surface (``append``, ``get``,
``append_tool_result``, ``append_assistant_tool_calls``, ``compact_tool_pair``,
``clear``) is unchanged; persistence is an internal side-effect.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from architect.config import settings

logger = logging.getLogger(__name__)


class ConversationHistory:
    def __init__(
        self,
        max_messages: int = 40,
        data_dir: Path | None = None,
    ) -> None:
        self._store: dict[int, list[dict[str, Any]]] = {}
        self._max = max_messages
        self._data_dir = data_dir if data_dir is not None else settings.data_dir / "history"
        self._load_all()

    def _path(self, channel_id: int) -> Path:
        return self._data_dir / f"{channel_id}.json"

    def _load_all(self) -> None:
        """Rebuild the store from JSON files on startup.

        Best-effort: corrupted or unreadable files are skipped with a
        warning — they don't break the bot, just lose that channel's
        history. New conversations will recreate the file.
        """
        if not self._data_dir.exists():
            return
        for path in self._data_dir.glob("*.json"):
            try:
                channel_id = int(path.stem)
            except ValueError:
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("failed to load history %s: %s", path, exc)
                continue
            messages = payload.get("messages")
            if isinstance(messages, list):
                self._store[channel_id] = messages

    def _save(self, channel_id: int) -> None:
        """Atomically persist a channel's history. Best-effort on failure."""
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            payload = {"messages": self._store.get(channel_id, [])}
            self._path(channel_id).write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as exc:
            logger.warning("failed to persist history for %d: %s", channel_id, exc)

    def _get_or_create(self, channel_id: int) -> list[dict[str, Any]]:
        if channel_id not in self._store:
            self._store[channel_id] = []
        return self._store[channel_id]

    def append(self, channel_id: int, role: str, content: str | list[Any]) -> None:
        """Append a message to the channel's history. role = 'user' | 'assistant'"""
        messages = self._get_or_create(channel_id)
        messages.append({"role": role, "content": content})
        if len(messages) > self._max:
            del messages[: len(messages) - self._max]
        self._save(channel_id)

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

    def append_assistant_tool_calls(
        self, channel_id: int, tool_calls_blocks: list[dict[str, Any]]
    ) -> None:
        """Append an assistant message containing tool_use blocks.

        In Anthropic format:
        {"role": "assistant", "content": [{"type": "tool_use", "id": "...", "name": "...", "input": {...}}]}
        """
        self.append(channel_id, "assistant", tool_calls_blocks)

    def get(self, channel_id: int) -> list[dict[str, Any]]:
        """Return the message history for a channel (empty list if no history)."""
        return self._store.get(channel_id, [])

    def clear(self, channel_id: int) -> None:
        """Clear the history for a channel (in-memory AND on disk)."""
        self._store.pop(channel_id, None)
        path = self._path(channel_id)
        if path.exists():
            try:
                path.unlink()
            except OSError as exc:
                logger.warning("failed to delete history %s: %s", path, exc)

    def compact_tool_pair(self, channel_id: int, tool_use_id: str, summary: str) -> bool:
        """Collapse the (assistant tool_use, user tool_result) pair for `tool_use_id`
        into a single assistant text message containing `summary`.

        This keeps the conversation coherent ("a plan ran, here's what happened")
        while shedding the verbose tool blocks that would otherwise dominate the
        rolling 40-message window. Returns True when the pair was found and
        replaced, False otherwise.
        """
        messages = self._store.get(channel_id)
        if not messages:
            return False

        use_idx = None
        for i, msg in enumerate(messages):
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            if any(
                block.get("type") == "tool_use" and block.get("id") == tool_use_id
                for block in content
            ):
                use_idx = i
                break
        if use_idx is None:
            return False

        result_idx = None
        for j in range(use_idx + 1, len(messages)):
            msg = messages[j]
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            if any(
                block.get("type") == "tool_result"
                and block.get("tool_use_id") == tool_use_id
                for block in content
            ):
                result_idx = j
                break

        replacement = {"role": "assistant", "content": summary}
        if result_idx is None:
            messages[use_idx] = replacement
        else:
            del messages[use_idx : result_idx + 1]
            messages.insert(use_idx, replacement)
        self._save(channel_id)
        return True
