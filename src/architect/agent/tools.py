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
    {
        # existing
        "create_category",
        "create_text_channel",
        "create_voice_channel",
        "create_role",
        "set_channel_permissions",
        # domain 1
        "create_forum_channel",
        "create_stage_channel",
        "edit_channel",
        "delete_channel",
        "create_invite",
        "delete_invite",
        "create_webhook",
        "edit_webhook",
        "delete_webhook",
        # domain 2
        "edit_role",
        "delete_role",
        "assign_role",
        "remove_role",
        # domain 3
        "edit_member",
        # domain 4
        "create_scheduled_event",
        "edit_scheduled_event",
        "delete_scheduled_event",
        # domain 5
        "create_automod_rule",
        "edit_automod_rule",
        "delete_automod_rule",
        # domain 6
        "edit_server",
        # domain 7
        "edit_welcome_screen",
    }
)

_ALL_ACTION_TYPES = sorted(MUTATION_TOOLS)  # sorted for deterministic order across restarts


def get_tools() -> list[dict]:
    return [
        # ── Existing ──────────────────────────────────────────────────────────
        {
            "name": "create_category",
            "description": "Create a Discord category in the guild.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Category name"},
                },
                "required": ["name"],
            },
        },
        {
            "name": "create_text_channel",
            "description": "Create a text channel, optionally inside a category.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Channel name"},
                    "category": {
                        "type": "string",
                        "description": "Category name parente (optionnel)",
                    },
                },
                "required": ["name"],
            },
        },
        {
            "name": "create_voice_channel",
            "description": "Create a voice channel, optionally inside a category.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Voice channel name"},
                    "category": {
                        "type": "string",
                        "description": "Category name parente (optionnel)",
                    },
                },
                "required": ["name"],
            },
        },
        {
            "name": "create_role",
            "description": "Create a Discord role.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Role name"},
                    "color": {
                        "type": "string",
                        "description": "Role hex color, e.g. '#3498DB' (optional)",
                    },
                    "mentionable": {
                        "type": "boolean",
                        "description": "Whether the role is mentionable (optional)",
                    },
                },
                "required": ["name"],
            },
        },
        {
            "name": "set_channel_permissions",
            "description": "Set channel permissions for a role.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Channel name"},
                    "role": {"type": "string", "description": "Role name"},
                    "allow": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Permissions to allow (optional)",
                    },
                    "deny": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Permissions to deny (optional)",
                    },
                },
                "required": ["channel", "role"],
            },
        },
        # ── Domain 1 — Channels ───────────────────────────────────────────────
        {
            "name": "create_forum_channel",
            "description": "Create a Discord forum channel (threads with tags).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Forum name"},
                    "category": {"type": "string", "description": "Parent category (optional)"},
                    "topic": {
                        "type": "string",
                        "description": "Forum description, max 4096 chars (optional)",
                    },
                    "slowmode": {
                        "type": "integer",
                        "description": "Per-user message delay in seconds, 0-21600 (optional)",
                    },
                    "nsfw": {"type": "boolean", "description": "Adult content flag (optional)"},
                    "available_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Available tag names, max 20 (optional)",
                    },
                    "require_tag": {
                        "type": "boolean",
                        "description": "Require a tag on each thread (optional)",
                    },
                    "default_sort_order": {
                        "type": "string",
                        "enum": ["latest_activity", "creation_date"],
                        "description": "Thread sort order (optional)",
                    },
                    "default_forum_layout": {
                        "type": "string",
                        "enum": ["list", "gallery"],
                        "description": "Default forum layout (optional)",
                    },
                },
                "required": ["name"],
            },
        },
        {
            "name": "create_stage_channel",
            "description": "Create a Stage channel (conferences/podcasts).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Stage name"},
                    "category": {"type": "string", "description": "Parent category (optional)"},
                    "bitrate": {
                        "type": "integer",
                        "description": "Audio quality in bps (optional)",
                    },
                    "user_limit": {
                        "type": "integer",
                        "description": "User limit 0-10000 (optional)",
                    },
                    "rtc_region": {
                        "type": "string",
                        "description": "Voice region override, null = auto (optional)",
                    },
                    "position": {
                        "type": "integer",
                        "description": "Position in the list (optional)",
                    },
                },
                "required": ["name"],
            },
        },
        {
            "name": "edit_channel",
            "description": "Edit an existing channel or category (rename, topic, slowmode, nsfw, position, bitrate, etc.).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Channel name or ID"},
                    "name": {"type": "string", "description": "New name (optional)"},
                    "topic": {
                        "type": "string",
                        "description": "Channel topic, max 1024 chars (optional)",
                    },
                    "slowmode": {
                        "type": "integer",
                        "description": "Slowmode delay in seconds, 0-21600 (optional)",
                    },
                    "nsfw": {"type": "boolean", "description": "Adult content flag (optional)"},
                    "position": {
                        "type": "integer",
                        "description": "Position in the list (optional)",
                    },
                    "bitrate": {
                        "type": "integer",
                        "description": "Audio quality in bps, voice/stage only (optional)",
                    },
                    "user_limit": {
                        "type": "integer",
                        "description": "Member limit, voice: 0-99 (optional)",
                    },
                    "parent_id": {
                        "type": "string",
                        "description": "Move to this category (name or ID) (optional)",
                    },
                    "rtc_region": {
                        "type": "string",
                        "description": "Voice region override (optional)",
                    },
                    "video_quality_mode": {
                        "type": "string",
                        "enum": ["auto", "full"],
                        "description": "Voice/stage video quality (optional)",
                    },
                    "default_auto_archive_duration": {
                        "type": "integer",
                        "enum": [60, 1440, 4320, 10080],
                        "description": "Thread auto-archive duration in minutes (optional)",
                    },
                },
                "required": ["channel"],
            },
        },
        {
            "name": "delete_channel",
            "description": "Permanently delete a channel or category. IRREVERSIBLE.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "description": "Channel name or ID to delete",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Deletion reason (optional)",
                    },
                },
                "required": ["channel"],
            },
        },
        {
            "name": "create_invite",
            "description": "Create an invite link for a channel.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Channel name or ID"},
                    "max_age": {
                        "type": "integer",
                        "description": "Validity in seconds, 0 = permanent, max 604800 (optional)",
                    },
                    "max_uses": {
                        "type": "integer",
                        "description": "Max uses, 0 = unlimited, max 100 (optional)",
                    },
                    "temporary": {
                        "type": "boolean",
                        "description": "Kick if no role assigned (optional)",
                    },
                },
                "required": ["channel"],
            },
        },
        {
            "name": "delete_invite",
            "description": "Revoke an invite link by its code.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Invite code (e.g. 'xKy3h2')",
                    },
                },
                "required": ["code"],
            },
        },
        {
            "name": "create_webhook",
            "description": "Create an incoming webhook on a channel.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Channel name or ID"},
                    "name": {"type": "string", "description": "Webhook name"},
                },
                "required": ["channel", "name"],
            },
        },
        {
            "name": "edit_webhook",
            "description": "Rename a webhook or move it to another channel.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "webhook": {"type": "string", "description": "Webhook name or ID"},
                    "name": {"type": "string", "description": "New name (optional)"},
                    "channel": {
                        "type": "string",
                        "description": "Move to this channel (name or ID) (optional)",
                    },
                },
                "required": ["webhook"],
            },
        },
        {
            "name": "delete_webhook",
            "description": "Delete a webhook.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "webhook": {"type": "string", "description": "Webhook name or ID"},
                },
                "required": ["webhook"],
            },
        },
        # ── Domain 2 — Roles ──────────────────────────────────────────────────
        {
            "name": "edit_role",
            "description": "Edit an existing role (name, color, hoist, mentionable). Forbidden on @everyone.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "description": "Role name or ID"},
                    "name": {"type": "string", "description": "New name (optional)"},
                    "color": {"type": "string", "description": "Hex color '#RRGGBB' (optional)"},
                    "hoist": {
                        "type": "boolean",
                        "description": "Display separately in the member list (optional)",
                    },
                    "mentionable": {
                        "type": "boolean",
                        "description": "Allow @mentions (optional)",
                    },
                },
                "required": ["role"],
            },
        },
        {
            "name": "delete_role",
            "description": "Delete a role. IRREVERSIBLE. Forbidden on @everyone.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "description": "Role name or ID"},
                    "reason": {"type": "string", "description": "Reason (optional)"},
                },
                "required": ["role"],
            },
        },
        {
            "name": "assign_role",
            "description": "Assign a role to a member (via @mention or user_id).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "user": {"type": "string", "description": "@mention or numeric user_id"},
                    "role": {"type": "string", "description": "Role name or ID"},
                },
                "required": ["user", "role"],
            },
        },
        {
            "name": "remove_role",
            "description": "Remove a role from a member.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "user": {"type": "string", "description": "@mention or numeric user_id"},
                    "role": {"type": "string", "description": "Role name or ID"},
                },
                "required": ["user", "role"],
            },
        },
        # ── Domain 3 — Members ────────────────────────────────────────────────
        {
            "name": "edit_member",
            "description": "Edit a member: nickname, server mute/deafen, timeout, move to a voice channel.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "user": {"type": "string", "description": "@mention or numeric user_id"},
                    "nick": {
                        "type": "string",
                        "description": "Nouveau surnom, null pour reset (optionnel)",
                    },
                    "mute": {"type": "boolean", "description": "Mute serveur en vocal (optionnel)"},
                    "deaf": {
                        "type": "boolean",
                        "description": "Sourd serveur en vocal (optionnel)",
                    },
                    "timeout_until": {
                        "type": "string",
                        "description": "ISO8601 UTC datetime until the timeout lasts, null to remove (optional)",
                    },
                    "move_to_channel": {
                        "type": "string",
                        "description": "Voice channel name or ID to move the member to (optional)",
                    },
                },
                "required": ["user"],
            },
        },
        # ── Domain 4 — Scheduled Events ───────────────────────────────────────
        {
            "name": "create_scheduled_event",
            "description": "Create a Discord scheduled event (voice, stage, or external).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Event title"},
                    "start_time": {
                        "type": "string",
                        "description": "ISO8601 UTC start, e.g. '2026-05-01T18:00:00Z'",
                    },
                    "entity_type": {
                        "type": "string",
                        "enum": ["voice", "stage", "external"],
                        "description": "Type: 'voice' (voice channel), 'stage' (stage), 'external' (physical location)",
                    },
                    "channel": {
                        "type": "string",
                        "description": "Voice/stage channel name or ID (required for voice/stage)",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "Fin ISO8601 UTC (requis pour external, optionnel sinon)",
                    },
                    "location": {
                        "type": "string",
                        "description": "Lieu physique (requis pour external)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Event description (optional)",
                    },
                },
                "required": ["name", "start_time", "entity_type"],
            },
        },
        {
            "name": "edit_scheduled_event",
            "description": "Edit a scheduled event or change its status.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "event": {"type": "string", "description": "Event name or ID"},
                    "name": {"type": "string", "description": "Nouveau titre (optionnel)"},
                    "start_time": {
                        "type": "string",
                        "description": "New ISO8601 start time (optional)",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "Nouvelle heure de fin ISO8601 (optionnel)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Nouvelle description (optionnel)",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "completed", "canceled"],
                        "description": "Transition de statut (optionnel)",
                    },
                },
                "required": ["event"],
            },
        },
        {
            "name": "delete_scheduled_event",
            "description": "Delete a scheduled event.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "event": {"type": "string", "description": "Event name or ID"},
                },
                "required": ["event"],
            },
        },
        # ── Domain 5 — AutoMod ────────────────────────────────────────────────
        {
            "name": "create_automod_rule",
            "description": "Create an AutoMod rule (keyword filter, spam, excessive mentions).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Rule name"},
                    "event_type": {
                        "type": "string",
                        "enum": ["message_send", "member_update"],
                        "description": "Watched event",
                    },
                    "trigger_type": {
                        "type": "string",
                        "enum": ["keyword", "spam", "keyword_preset", "mention_spam"],
                        "description": "Trigger type",
                    },
                    "actions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Actions : 'block_message', 'send_alert:<channel>', 'timeout:<secondes>'",
                    },
                    "keyword_filter": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Keywords to block for the 'keyword' trigger (optional)",
                    },
                    "regex_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Patterns regex Rust max 10 (optionnel)",
                    },
                    "allow_list": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Allow-listed words (optional)",
                    },
                    "presets": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["profanity", "sexual_content", "slurs"],
                        },
                        "description": "Built-in presets for the 'keyword_preset' trigger (optional)",
                    },
                    "mention_limit": {
                        "type": "integer",
                        "description": "Nb max de mentions uniques pour trigger 'mention_spam' (1-50) (optionnel)",
                    },
                    "exempt_roles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Exempt roles (names or IDs), max 20 (optional)",
                    },
                    "exempt_channels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Exempt channels (names or IDs), max 50 (optional)",
                    },
                    "enabled": {
                        "type": "boolean",
                        "description": "Enable the rule (default false) (optional)",
                    },
                },
                "required": ["name", "event_type", "trigger_type", "actions"],
            },
        },
        {
            "name": "edit_automod_rule",
            "description": "Edit an existing AutoMod rule.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "rule": {"type": "string", "description": "Rule name or ID"},
                    "name": {"type": "string", "description": "New name (optional)"},
                    "enabled": {"type": "boolean", "description": "Enable/disable (optional)"},
                    "keyword_filter": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "New keywords (optional)",
                    },
                    "regex_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Nouveaux regex (optionnel)",
                    },
                    "allow_list": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Nouvelle liste blanche (optionnel)",
                    },
                    "actions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Nouvelles actions (optionnel)",
                    },
                    "exempt_roles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Exempt roles (optional)",
                    },
                    "exempt_channels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Exempt channels (optional)",
                    },
                },
                "required": ["rule"],
            },
        },
        {
            "name": "delete_automod_rule",
            "description": "Delete an AutoMod rule.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "rule": {"type": "string", "description": "Rule name or ID"},
                },
                "required": ["rule"],
            },
        },
        # ── Domain 6 — Server Settings ────────────────────────────────────────
        {
            "name": "edit_server",
            "description": "Edit Discord server settings (verification level, filters, system channels, locale, etc.).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nouveau nom du serveur (optionnel)"},
                    "verification_level": {
                        "type": "string",
                        "enum": ["none", "low", "medium", "high", "highest"],
                        "description": "Verification level for new members (optional)",
                    },
                    "default_message_notifications": {
                        "type": "string",
                        "enum": ["all_messages", "only_mentions"],
                        "description": "Default notifications for new members (optional)",
                    },
                    "explicit_content_filter": {
                        "type": "string",
                        "enum": ["disabled", "members_without_roles", "all_members"],
                        "description": "Niveau de filtrage du contenu explicite (optionnel)",
                    },
                    "afk_channel": {
                        "type": "string",
                        "description": "AFK voice channel name or ID, null to disable (optional)",
                    },
                    "afk_timeout": {
                        "type": "integer",
                        "enum": [60, 300, 900, 1800, 3600],
                        "description": "AFK delay in seconds (optional)",
                    },
                    "system_channel": {
                        "type": "string",
                        "description": "Channel name or ID for system messages (welcome, boosts) (optional)",
                    },
                    "rules_channel": {
                        "type": "string",
                        "description": "Rules channel name or ID (community servers) (optional)",
                    },
                    "public_updates_channel": {
                        "type": "string",
                        "description": "Channel name or ID for Discord updates (community servers) (optional)",
                    },
                    "safety_alerts_channel": {
                        "type": "string",
                        "description": "Channel name or ID for Discord safety alerts (optional)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Community server description (optional)",
                    },
                    "preferred_locale": {
                        "type": "string",
                        "description": "Preferred locale, e.g. 'fr', 'en-US', 'de' (optional)",
                    },
                    "premium_progress_bar_enabled": {
                        "type": "boolean",
                        "description": "Afficher la barre de progression des boosts (optionnel)",
                    },
                },
            },
        },
        # ── Domain 7 — Welcome Screen ─────────────────────────────────────────
        {
            "name": "edit_welcome_screen",
            "description": "Edit the welcome screen of a community server.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "enabled": {
                        "type": "boolean",
                        "description": "Enable the welcome screen (optional)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Welcome text shown (optional)",
                    },
                    "welcome_channels": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "channel": {
                                    "type": "string",
                                    "description": "Channel name or ID",
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Courte description",
                                },
                                "emoji": {
                                    "type": "string",
                                    "description": "Emoji Unicode (optionnel)",
                                },
                            },
                            "required": ["channel", "description"],
                        },
                        "description": "Channels mis en avant, max 5 (optionnel)",
                    },
                },
            },
        },
        # ── Read-only ─────────────────────────────────────────────────────────
        {
            "name": "list_channels",
            "description": "List the guild's channels and categories.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "list_roles",
            "description": "List the guild's roles.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "get_member_roles",
            "description": "List a member's current roles.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "user": {"type": "string", "description": "@mention or numeric user_id"},
                },
                "required": ["user"],
            },
        },
        {
            "name": "get_server_info",
            "description": "Return current server settings (verification level, filters, locale, boost, etc.).",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "list_invites",
            "description": "Liste les invitations actives du serveur.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "list_webhooks",
            "description": "Liste les webhooks du serveur.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "list_scheduled_events",
            "description": "List the server's scheduled events.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "list_automod_rules",
            "description": "List the server's AutoMod rules.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "check_bot_permissions",
            "description": (
                "Check the Discord permissions currently granted to the bot. "
                "Call this before generate_plan if the plan involves mutations likely "
                "to fail (role management, AutoMod, server settings). Avoid proposing "
                "a plan that will fail at execution time."
            ),
            "input_schema": {"type": "object", "properties": {}},
        },
        # ── Meta ──────────────────────────────────────────────────────────────
        {
            "name": "ask_clarification",
            "description": "Ask the user a question to clarify their request before acting.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to ask the user",
                    },
                },
                "required": ["question"],
            },
        },
        {
            "name": "generate_plan",
            "description": "Generate a complete Discord configuration plan. Use this tool when the request implies creating or modifying several items in a single operation. The plan will be shown to the user for validation before any execution.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Titre du plan (ex: 'Serveur Gaming Pro')",
                    },
                    "actions": {
                        "type": "array",
                        "description": "Ordered list of actions to execute",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": _ALL_ACTION_TYPES,
                                    "description": "Type d'action",
                                },
                                "params": {
                                    "type": "object",
                                    "description": "Action parameters",
                                },
                            },
                            "required": ["type", "params"],
                        },
                    },
                },
                "required": ["title", "actions"],
            },
        },
    ]
