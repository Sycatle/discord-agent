from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


@dataclass
class ReplyEvent:
    text: str


@dataclass
class ToolCallEvent:
    tool_name: str
    params: dict
    tool_use_id: str


@dataclass
class ConfirmationRequiredEvent(ToolCallEvent):
    pass


@dataclass
class ReadOnlyToolEvent(ToolCallEvent):
    pass


@dataclass
class ClarificationEvent:
    question: str


AgentEvent: TypeAlias = ReplyEvent | ConfirmationRequiredEvent | ReadOnlyToolEvent | ClarificationEvent
