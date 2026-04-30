from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ReplyEvent:
    text: str


@dataclass
class ToolCallEvent:
    tool_name: str
    params: dict[str, Any]
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


@dataclass
class PlanGeneratedEvent:
    title: str
    actions: list[dict[str, Any]]
    tool_use_id: str


type AgentEvent = (
    ReplyEvent
    | ConfirmationRequiredEvent
    | ReadOnlyToolEvent
    | ClarificationEvent
    | PlanGeneratedEvent
)
