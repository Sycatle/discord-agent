"""Pydantic models describing the parameters of every ``ActionType``.

Each handler in ``architect.executor.handlers`` consumes one of these models;
``architect.agent.tools`` uses them as the single source of truth for the
JSON Schema sent to the LLM. All models forbid extra fields so the LLM
cannot smuggle unexpected parameters past the whitelist.
"""

from architect.models.params.automod import (
    CreateAutoModRuleParams,
    DeleteAutoModRuleParams,
    EditAutoModRuleParams,
)
from architect.models.params.channels import (
    CreateCategoryParams,
    CreateForumChannelParams,
    CreateInviteParams,
    CreateStageChannelParams,
    CreateTextChannelParams,
    CreateVoiceChannelParams,
    CreateWebhookParams,
    DeleteChannelParams,
    DeleteInviteParams,
    DeleteWebhookParams,
    EditChannelParams,
    EditWebhookParams,
    SetChannelPermissionsParams,
)
from architect.models.params.events import (
    CreateScheduledEventParams,
    DeleteScheduledEventParams,
    EditScheduledEventParams,
)
from architect.models.params.members import EditMemberParams
from architect.models.params.roles import (
    AssignRoleParams,
    CreateRoleParams,
    DeleteRoleParams,
    EditRoleParams,
    RemoveRoleParams,
)
from architect.models.params.server import (
    EditServerParams,
    EditWelcomeScreenParams,
    WelcomeChannelEntry,
)

__all__ = [
    "AssignRoleParams",
    "CreateAutoModRuleParams",
    "CreateCategoryParams",
    "CreateForumChannelParams",
    "CreateInviteParams",
    "CreateRoleParams",
    "CreateScheduledEventParams",
    "CreateStageChannelParams",
    "CreateTextChannelParams",
    "CreateVoiceChannelParams",
    "CreateWebhookParams",
    "DeleteAutoModRuleParams",
    "DeleteChannelParams",
    "DeleteInviteParams",
    "DeleteRoleParams",
    "DeleteScheduledEventParams",
    "DeleteWebhookParams",
    "EditAutoModRuleParams",
    "EditChannelParams",
    "EditMemberParams",
    "EditRoleParams",
    "EditScheduledEventParams",
    "EditServerParams",
    "EditWebhookParams",
    "EditWelcomeScreenParams",
    "RemoveRoleParams",
    "SetChannelPermissionsParams",
    "WelcomeChannelEntry",
]
