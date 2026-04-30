"""Rollback mapping for the atomic batch mode.

For each ``create_*`` action that has a deterministic inverse we record
the corresponding deletion action and how to translate the original
parameters into the inverse call. Actions without an entry here
(``create_invite``, ``edit_*``, ``delete_*``) are not rollback-able and
will be skipped by the rollback routine.
"""

from __future__ import annotations

ROLLBACK_ACTIONS: dict[str, tuple[str, dict[str, str]]] = {
    "create_category": ("delete_channel", {"channel": "name"}),
    "create_text_channel": ("delete_channel", {"channel": "name"}),
    "create_voice_channel": ("delete_channel", {"channel": "name"}),
    "create_forum_channel": ("delete_channel", {"channel": "name"}),
    "create_stage_channel": ("delete_channel", {"channel": "name"}),
    "create_role": ("delete_role", {"role": "name"}),
    "create_webhook": ("delete_webhook", {"webhook": "name"}),
    "create_scheduled_event": ("delete_scheduled_event", {"event": "name"}),
    "create_automod_rule": ("delete_automod_rule", {"rule": "name"}),
}
