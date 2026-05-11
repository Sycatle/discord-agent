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


@dataclass
class RecordPreferenceEvent:
    """Agent decided to persist a durable preference or decision for the guild.

    `kind` is "preference" (style/naming/scope constraints) or "decision"
    (record of a user choice made in the past — e.g. user refused AutoMod).
    """

    text: str
    kind: str
    tool_use_id: str


@dataclass
class RecordFindingEvent:
    """Agent recorded an audit observation (risk / health / opportunity)."""

    category: str
    summary: str
    severity: int
    tool_use_id: str


type AgentEvent = (
    ReplyEvent
    | ConfirmationRequiredEvent
    | ReadOnlyToolEvent
    | ClarificationEvent
    | PlanGeneratedEvent
    | RecordPreferenceEvent
    | RecordFindingEvent
)
