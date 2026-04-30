"""Required Discord permission per mutation tool.

Checked by ``Executor.execute`` before dispatching so we can surface a
clear human-readable error instead of a Discord 403. Read-only and meta
tools are intentionally absent — they don't mutate state.
"""

from __future__ import annotations

REQUIRED_PERMISSIONS: dict[str, str] = {
    "create_category": "manage_channels",
    "create_text_channel": "manage_channels",
    "create_voice_channel": "manage_channels",
    "create_forum_channel": "manage_channels",
    "create_stage_channel": "manage_channels",
    "edit_channel": "manage_channels",
    "delete_channel": "manage_channels",
    "set_channel_permissions": "manage_channels",
    "create_invite": "create_instant_invite",
    "delete_invite": "manage_channels",
    "create_webhook": "manage_webhooks",
    "edit_webhook": "manage_webhooks",
    "delete_webhook": "manage_webhooks",
    "create_role": "manage_roles",
    "edit_role": "manage_roles",
    "delete_role": "manage_roles",
    "assign_role": "manage_roles",
    "remove_role": "manage_roles",
    "edit_member": "moderate_members",
    "create_scheduled_event": "manage_events",
    "edit_scheduled_event": "manage_events",
    "delete_scheduled_event": "manage_events",
    "create_automod_rule": "manage_guild",
    "edit_automod_rule": "manage_guild",
    "delete_automod_rule": "manage_guild",
    "edit_server": "manage_guild",
    "edit_welcome_screen": "manage_guild",
}
