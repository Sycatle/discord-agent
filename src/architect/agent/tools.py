"""LLM tool catalogue.

The list of tools we send to Claude/OpenAI is generated from the same
``HANDLERS`` registry the executor dispatches on, plus two meta tools the
agent emits but doesn't execute (``ask_clarification`` and
``generate_plan``). Each tool's JSON Schema is produced by Pydantic from
the per-action models defined in ``architect.models.params``, so the
schema and the runtime validation are guaranteed to match.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from architect.executor.handlers import HANDLERS

READONLY_TOOLS: frozenset[str] = frozenset(
    {
        "list_channels",
        "list_roles",
        "get_member_roles",
        "get_server_info",
        "list_invites",
        "list_webhooks",
        "list_scheduled_events",
        "list_automod_rules",
        "check_bot_permissions",
    }
)

META_TOOLS: frozenset[str] = frozenset({"ask_clarification", "generate_plan"})

MUTATION_TOOLS: frozenset[str] = frozenset(
    name for name in HANDLERS if name not in READONLY_TOOLS
)


# ── Meta tools ──────────────────────────────────────────────────────────────


class AskClarificationParams(BaseModel):
    """Ask the user a question to clarify their request before acting."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(description="The question to ask the user")


class _PlannedAction(BaseModel):
    """A single action inside a generated plan."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(description="Action type, e.g. 'create_text_channel'")
    params: dict[str, Any] = Field(description="Action parameters")


class GeneratePlanParams(BaseModel):
    """Generate a complete Discord configuration plan.

    Use this tool when the request implies creating or modifying several
    items in a single operation. The plan will be shown to the user for
    validation before any execution.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(description="Plan title")
    actions: list[_PlannedAction] = Field(description="Ordered list of actions to execute")


_META_MODELS: dict[str, type[BaseModel]] = {
    "ask_clarification": AskClarificationParams,
    "generate_plan": GeneratePlanParams,
}


# ── Schema generation ───────────────────────────────────────────────────────


def _inline_refs(node: Any, defs: dict[str, Any]) -> Any:
    """Recursively replace ``$ref`` pointers with their resolved definitions.

    Pydantic emits a ``$defs`` section and ``{"$ref": "#/$defs/Name"}``
    pointers for nested models. The Anthropic tools API accepts that, but
    inlined schemas are easier to read in tests and logs.
    """
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            target = defs.get(ref.removeprefix("#/$defs/"))
            if target is not None:
                return _inline_refs(dict(target), defs)
        return {k: _inline_refs(v, defs) for k, v in node.items()}
    if isinstance(node, list):
        return [_inline_refs(item, defs) for item in node]
    return node


def _to_input_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Convert a Pydantic model into an Anthropic-compatible input_schema.

    Strips Pydantic-generated ``title``/``description`` at the schema root
    (we surface those at the tool level instead), inlines ``$ref``
    pointers, and drops the now-empty ``$defs`` section.
    """
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {}) or schema.pop("definitions", {})
    inlined: dict[str, Any] = _inline_refs(schema, defs)
    inlined.pop("title", None)
    inlined.pop("description", None)
    return inlined


def _description_for(model: type[BaseModel]) -> str:
    """Return the human-readable description for a tool.

    We use the model's docstring rather than ``model_json_schema()['description']``
    because Pydantic strips trailing newlines and re-flows the text in a way
    that's harder to read in Discord-facing logs.
    """
    doc = (model.__doc__ or "").strip()
    return " ".join(line.strip() for line in doc.splitlines() if line.strip())


def _tool(name: str, model: type[BaseModel]) -> dict[str, Any]:
    return {
        "name": name,
        "description": _description_for(model),
        "input_schema": _to_input_schema(model),
    }


def _patch_generate_plan_action_enum(tool: dict[str, Any]) -> None:
    """Inject the list of known mutation tool names as an enum on
    ``generate_plan.actions[*].type``.

    Pydantic can't express ``Literal[*MUTATION_TOOLS]`` at runtime without
    ugly metaprogramming; patching the inlined JSON schema is simpler and
    keeps the model definition readable.
    """
    items = tool["input_schema"]["properties"]["actions"]["items"]
    items.setdefault("properties", {}).setdefault("type", {})["enum"] = sorted(MUTATION_TOOLS)


def get_tools() -> list[dict[str, Any]]:
    """Return the full LLM tool list, generated from the registry + meta models."""
    tools: list[dict[str, Any]] = []
    for name, spec in HANDLERS.items():
        tools.append(_tool(name, spec.params_model))
    for name, model in _META_MODELS.items():
        tools.append(_tool(name, model))
    for tool in tools:
        if tool["name"] == "generate_plan":
            _patch_generate_plan_action_enum(tool)
    return tools
