from enum import StrEnum
from typing import Any
from pydantic import BaseModel


class ActionType(StrEnum):
    # Existing
    CREATE_CATEGORY = "create_category"
    CREATE_TEXT_CHANNEL = "create_text_channel"
    CREATE_VOICE_CHANNEL = "create_voice_channel"
    CREATE_ROLE = "create_role"
    SET_CHANNEL_PERMISSIONS = "set_channel_permissions"

    # Domain 1 — Channels
    CREATE_FORUM_CHANNEL = "create_forum_channel"
    CREATE_STAGE_CHANNEL = "create_stage_channel"
    EDIT_CHANNEL = "edit_channel"
    DELETE_CHANNEL = "delete_channel"
    CREATE_INVITE = "create_invite"
    DELETE_INVITE = "delete_invite"
    CREATE_WEBHOOK = "create_webhook"
    EDIT_WEBHOOK = "edit_webhook"
    DELETE_WEBHOOK = "delete_webhook"

    # Domain 2 — Roles
    EDIT_ROLE = "edit_role"
    DELETE_ROLE = "delete_role"
    ASSIGN_ROLE = "assign_role"
    REMOVE_ROLE = "remove_role"

    # Domain 3 — Members
    EDIT_MEMBER = "edit_member"

    # Domain 4 — Scheduled Events
    CREATE_SCHEDULED_EVENT = "create_scheduled_event"
    EDIT_SCHEDULED_EVENT = "edit_scheduled_event"
    DELETE_SCHEDULED_EVENT = "delete_scheduled_event"

    # Domain 5 — AutoMod
    CREATE_AUTOMOD_RULE = "create_automod_rule"
    EDIT_AUTOMOD_RULE = "edit_automod_rule"
    DELETE_AUTOMOD_RULE = "delete_automod_rule"

    # Domain 6 — Server Settings
    EDIT_SERVER = "edit_server"

    # Domain 7 — Welcome Screen
    EDIT_WELCOME_SCREEN = "edit_welcome_screen"


class Action(BaseModel):
    type: ActionType
    params: dict[str, Any]
