"""Topological layering of action plans for parallel execution.

Given a list of actions (produced by ``generate_plan``), ``build_layers``
returns the indices of each action grouped into layers such that:

- actions in the same layer are independent and can run concurrently;
- a layer never starts until the previous layer is fully complete.

The dependency model is intentionally name-based: an action that
*produces* a name (``create_*`` actions, ``create_automod_rule``) is a
prerequisite of any later action that *consumes* that same name
(``category``, ``parent_id``, ``role``, ``channel``, ``rule``...).
Order within the plan is preserved as a tie-breaker — if action B is
known to depend on action A, B lives in a layer with index strictly
greater than A's. Actions touching the same object by name share the
same layer transitively (e.g. successive ``edit_channel`` calls on the
same channel run in sequence, not parallel — preserving the user-stated
intent ordering).
"""

from __future__ import annotations

from typing import Any

_NAME_PRODUCERS: dict[str, str] = {
    "create_category": "name",
    "create_text_channel": "name",
    "create_voice_channel": "name",
    "create_forum_channel": "name",
    "create_stage_channel": "name",
    "create_role": "name",
    "create_webhook": "name",
    "create_scheduled_event": "name",
    "create_automod_rule": "name",
}

# Each consumer maps the action type to the list of param keys whose values
# are the names it depends on. ``edit_channel.channel`` and the cross-type
# touching are handled separately by the same-target logic below.
_NAME_CONSUMERS: dict[str, list[str]] = {
    "create_text_channel": ["category"],
    "create_voice_channel": ["category"],
    "create_forum_channel": ["category"],
    "create_stage_channel": ["category"],
    "edit_channel": ["parent_id"],
    "set_channel_permissions": ["channel", "role"],
    "assign_role": ["role"],
    "remove_role": ["role"],
    "delete_channel": ["channel"],
    "delete_role": ["role"],
    "delete_webhook": ["webhook"],
    "delete_scheduled_event": ["event"],
    "delete_automod_rule": ["rule"],
    "edit_role": ["role"],
    "edit_webhook": ["webhook"],
    "edit_scheduled_event": ["event"],
    "edit_automod_rule": ["rule"],
}

# Target keys that identify "the same object" for ordering — two actions
# pointing at the same target name MUST stay in plan-order even if neither
# strictly produces/consumes the other (e.g. two `edit_channel` calls on
# the same channel). Maps action_type → param key holding the target name.
_TARGET_KEYS: dict[str, str] = {
    "edit_channel": "channel",
    "delete_channel": "channel",
    "set_channel_permissions": "channel",
    "edit_role": "role",
    "delete_role": "role",
    "assign_role": "role",
    "remove_role": "role",
    "edit_webhook": "webhook",
    "delete_webhook": "webhook",
    "edit_scheduled_event": "event",
    "delete_scheduled_event": "event",
    "edit_automod_rule": "rule",
    "delete_automod_rule": "rule",
}


def _produced_name(action: dict[str, Any]) -> str | None:
    key = _NAME_PRODUCERS.get(action.get("type", ""))
    if key is None:
        return None
    value = (action.get("params") or {}).get(key)
    return value if isinstance(value, str) and value else None


def _consumed_names(action: dict[str, Any]) -> set[str]:
    keys = _NAME_CONSUMERS.get(action.get("type", ""))
    if not keys:
        return set()
    params = action.get("params") or {}
    names: set[str] = set()
    for k in keys:
        v = params.get(k)
        if isinstance(v, str) and v:
            names.add(v)
    return names


def _target_name(action: dict[str, Any]) -> str | None:
    key = _TARGET_KEYS.get(action.get("type", ""))
    if key is None:
        return None
    v = (action.get("params") or {}).get(key)
    return v if isinstance(v, str) and v else None


def build_layers(actions: list[dict[str, Any]]) -> list[list[int]]:
    """Group action indices into topological layers.

    Returns ``[[indices_layer_0], [indices_layer_1], ...]``. Each layer is
    safe to schedule with ``asyncio.gather``; layers MUST be awaited in
    order.

    Empty input returns an empty list. Cycles are not possible by
    construction: dependencies only flow strictly forward in plan order.
    """
    if not actions:
        return []

    n = len(actions)
    depth: list[int] = [0] * n  # layer index assigned per action

    # Latest layer at which a given produced name became available.
    produced_at: dict[str, int] = {}
    # Latest layer at which a given target name was touched (any way).
    touched_at: dict[str, int] = {}

    for i, action in enumerate(actions):
        layer = 0
        # Honour consumed names: must run AFTER the producer's layer.
        for name in _consumed_names(action):
            if name in produced_at:
                layer = max(layer, produced_at[name] + 1)
            if name in touched_at:
                # If a prior action mutated/deleted this same name, we
                # must serialise relative to it as well.
                layer = max(layer, touched_at[name] + 1)
        # Honour same-target ordering: stay strictly after the previous
        # touch of the same object so successive edits/deletes serialise.
        target = _target_name(action)
        if target is not None:
            if target in touched_at:
                layer = max(layer, touched_at[target] + 1)
            if target in produced_at:
                layer = max(layer, produced_at[target] + 1)

        # delete_*+create_same_name race: if this action produces a name
        # that was just deleted, push it past the delete.
        produced = _produced_name(action)
        if produced is not None and produced in touched_at:
            layer = max(layer, touched_at[produced] + 1)

        depth[i] = layer
        if produced is not None:
            produced_at[produced] = layer
        if target is not None:
            touched_at[target] = layer
        # delete_channel/role consume the name AND remove it; record under
        # touched_at so a subsequent create_* same name is forced later.
        if action.get("type", "").startswith("delete_") and target is not None:
            touched_at[target] = layer

    max_layer = max(depth) if depth else -1
    layers: list[list[int]] = [[] for _ in range(max_layer + 1)]
    for i, d in enumerate(depth):
        layers[d].append(i)
    return layers
