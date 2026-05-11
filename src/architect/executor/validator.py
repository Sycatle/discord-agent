"""Static plan validation: catch conflicts BEFORE any Discord call.

Runs in ``O(actions)`` with a single pass that maintains a virtual state of
what the plan will produce on top of the current ``GuildSnapshot``. Pure
Python — no Discord I/O.

The validator emits ``PlanIssue`` items partitioned by severity:

- ``error``: the plan is guaranteed to fail at exec time (e.g. ``edit_channel``
  targeting a channel that does not exist).
- ``warning``: the plan will probably work but signals churn or a likely
  Discord quirk (e.g. duplicate AutoMod trigger type, role above the bot's
  top role).

The bot layer decides what to do with errors (block exec, annotate the
preview, etc.). Today they are surfaced in the plan embed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from architect.models.snapshot import GuildSnapshot

_CHANNEL_CREATE_TYPES: frozenset[str] = frozenset(
    {
        "create_category",
        "create_text_channel",
        "create_voice_channel",
        "create_forum_channel",
        "create_stage_channel",
    }
)
_CATEGORY_CREATE_TYPES: frozenset[str] = frozenset({"create_category"})
_AUTOMOD_SINGLETON_TRIGGERS: frozenset[str] = frozenset({"spam", "mention_spam"})
_AUTOMOD_KEYWORD_CAP = 6  # Discord enforces 6 keyword + 1 of each other type


@dataclass(frozen=True, slots=True)
class PlanIssue:
    severity: str  # "error" | "warning"
    action_index: int
    message: str

    @property
    def is_error(self) -> bool:
        return self.severity == "error"


def _param(action: dict[str, Any], key: str, default: Any = None) -> Any:
    return action.get("params", {}).get(key, default)


def validate_plan(
    actions: list[dict[str, Any]], snapshot: GuildSnapshot
) -> list[PlanIssue]:
    """Return all detected issues in actions order.

    Algorithm: walk actions once, keeping virtual sets of (a) channels that
    will exist after the plan runs and (b) automod-rule counts per trigger
    type. Each action is checked against this rolling state, then the state
    is updated to reflect the action's effect.
    """
    issues: list[PlanIssue] = []
    if not actions:
        issues.append(
            PlanIssue(severity="warning", action_index=0, message="Empty plan.")
        )
        return issues

    # Virtual world: start from the current snapshot.
    existing_channel_names: set[str] = {c.name for c in snapshot.channels}
    existing_category_names: set[str] = {c.name for c in snapshot.categories}
    existing_role_names: set[str] = {r.name for r in snapshot.roles}
    deleted_channel_names: set[str] = set()
    deleted_role_names: set[str] = set()

    automod_trigger_counts: dict[str, int] = {}
    for r in snapshot.automod_rules:
        automod_trigger_counts[r.trigger_type] = (
            automod_trigger_counts.get(r.trigger_type, 0) + 1
        )

    seen_creates: dict[str, int] = {}  # name -> last action_index that created it

    for i, action in enumerate(actions):
        atype = action.get("type", "")
        params = action.get("params", {}) or {}

        # ── Channel creates ────────────────────────────────────────────────
        if atype in _CHANNEL_CREATE_TYPES:
            name = params.get("name")
            if not isinstance(name, str) or not name:
                issues.append(PlanIssue("error", i, f"`{atype}` missing `name`."))
                continue
            already_exists = (
                name in existing_channel_names or name in existing_category_names
            )
            if already_exists and name not in deleted_channel_names:
                issues.append(
                    PlanIssue(
                        "warning",
                        i,
                        f"`{name}` already exists — prefer `edit_channel` over `{atype}`.",
                    )
                )
            if name in seen_creates:
                issues.append(
                    PlanIssue(
                        "error",
                        i,
                        f"`{atype}` would create `{name}` twice "
                        f"(also at action #{seen_creates[name] + 1}).",
                    )
                )
            seen_creates[name] = i

            # Parent category check (if specified): must exist before this point.
            category = params.get("category")
            if category and atype != "create_category":
                cat_exists = (
                    category in existing_category_names
                    or category in {
                        actions[j].get("params", {}).get("name")
                        for j in range(i)
                        if actions[j].get("type") in _CATEGORY_CREATE_TYPES
                    }
                )
                if not cat_exists:
                    issues.append(
                        PlanIssue(
                            "error",
                            i,
                            f"`{atype}` references missing category `{category}`.",
                        )
                    )

            if atype == "create_category":
                existing_category_names.add(name)
            else:
                existing_channel_names.add(name)
            deleted_channel_names.discard(name)

        # ── Channel edit / delete ─────────────────────────────────────────
        elif atype in ("edit_channel", "delete_channel"):
            target = params.get("channel")
            if not isinstance(target, str) or not target:
                issues.append(PlanIssue("error", i, f"`{atype}` missing `channel`."))
                continue
            # Numeric ID is always considered valid (we can't easily check IDs).
            looks_numeric = target.isdigit()
            exists_now = (
                looks_numeric
                or target in existing_channel_names
                or target in existing_category_names
            )
            already_deleted = target in deleted_channel_names
            if not exists_now and not looks_numeric:
                issues.append(
                    PlanIssue(
                        "error",
                        i,
                        f"`{atype}` references unknown channel `{target}`.",
                    )
                )
            elif already_deleted:
                issues.append(
                    PlanIssue(
                        "error",
                        i,
                        f"`{atype}` references already-deleted channel `{target}`.",
                    )
                )
            if atype == "delete_channel" and target in seen_creates:
                issues.append(
                    PlanIssue(
                        "warning",
                        i,
                        f"`{target}` is created and deleted in the same plan — likely churn.",
                    )
                )
            if atype == "delete_channel":
                deleted_channel_names.add(target)
                existing_channel_names.discard(target)
                existing_category_names.discard(target)
            # parent_id reference check for edit_channel
            if atype == "edit_channel":
                parent = params.get("parent_id")
                if isinstance(parent, str) and parent and not parent.isdigit():
                    cat_known = (
                        parent in existing_category_names
                        or parent
                        in {
                            actions[j].get("params", {}).get("name")
                            for j in range(i)
                            if actions[j].get("type") in _CATEGORY_CREATE_TYPES
                        }
                    )
                    if not cat_known:
                        issues.append(
                            PlanIssue(
                                "error",
                                i,
                                f"`edit_channel` would move `{target}` "
                                f"under unknown category `{parent}`.",
                            )
                        )

        # ── Roles ─────────────────────────────────────────────────────────
        elif atype == "create_role":
            name = params.get("name")
            if not isinstance(name, str) or not name:
                issues.append(PlanIssue("error", i, "`create_role` missing `name`."))
                continue
            if name in existing_role_names and name not in deleted_role_names:
                issues.append(
                    PlanIssue(
                        "warning",
                        i,
                        f"Role `{name}` already exists — prefer `edit_role`.",
                    )
                )
            existing_role_names.add(name)

        elif atype in ("edit_role", "delete_role", "assign_role", "remove_role"):
            target = params.get("role")
            if not isinstance(target, str) or not target:
                issues.append(PlanIssue("error", i, f"`{atype}` missing `role`."))
                continue
            looks_numeric = target.isdigit()
            exists_now = looks_numeric or target in existing_role_names
            if not exists_now and not looks_numeric:
                issues.append(
                    PlanIssue("error", i, f"`{atype}` references unknown role `{target}`.")
                )
            if atype == "delete_role":
                deleted_role_names.add(target)
                existing_role_names.discard(target)

        # ── AutoMod ───────────────────────────────────────────────────────
        elif atype == "create_automod_rule":
            trigger = params.get("trigger_type")
            if not isinstance(trigger, str):
                issues.append(
                    PlanIssue("error", i, "`create_automod_rule` missing `trigger_type`.")
                )
                continue
            count = automod_trigger_counts.get(trigger, 0) + 1
            automod_trigger_counts[trigger] = count
            if trigger in _AUTOMOD_SINGLETON_TRIGGERS and count > 1:
                issues.append(
                    PlanIssue(
                        "warning",
                        i,
                        f"AutoMod trigger `{trigger}` already exists "
                        "— Discord enforces 1 rule per trigger type.",
                    )
                )
            if trigger == "keyword" and count > _AUTOMOD_KEYWORD_CAP:
                issues.append(
                    PlanIssue(
                        "warning",
                        i,
                        f"AutoMod keyword rules > {_AUTOMOD_KEYWORD_CAP} — "
                        "Discord rejects beyond that cap.",
                    )
                )

    return issues
