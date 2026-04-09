from enum import StrEnum
from typing import Any
from pydantic import BaseModel


class ActionType(StrEnum):
    CREATE_CATEGORY = "create_category"
    CREATE_TEXT_CHANNEL = "create_text_channel"
    CREATE_VOICE_CHANNEL = "create_voice_channel"
    CREATE_ROLE = "create_role"
    SET_CHANNEL_PERMISSIONS = "set_channel_permissions"


class Action(BaseModel):
    type: ActionType
    params: dict[str, Any]
