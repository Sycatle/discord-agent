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
from architect.models.params.emojis import (
    CreateEmojiParams,
    DeleteEmojiParams,
    DeleteStickerParams,
    RenameEmojiParams,
)
from architect.models.params.events import (
    CreateScheduledEventParams,
    DeleteScheduledEventParams,
    EditScheduledEventParams,
)
from architect.models.params.members import EditMemberParams
from architect.models.params.moderation import (
    BanMemberParams,
    BulkTimeoutMembersParams,
    KickMemberParams,
    UnbanMemberParams,
)
from architect.models.params.permissions import SetChannelPermissionOverridesParams
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
from architect.models.params.threads import (
    ArchiveThreadParams,
    CreateThreadParams,
    LockThreadParams,
    UnarchiveThreadParams,
)

__all__ = [
    "ArchiveThreadParams",
    "AssignRoleParams",
    "BanMemberParams",
    "BulkTimeoutMembersParams",
    "CreateAutoModRuleParams",
    "CreateCategoryParams",
    "CreateEmojiParams",
    "CreateForumChannelParams",
    "CreateInviteParams",
    "CreateRoleParams",
    "CreateScheduledEventParams",
    "CreateStageChannelParams",
    "CreateTextChannelParams",
    "CreateThreadParams",
    "CreateVoiceChannelParams",
    "CreateWebhookParams",
    "DeleteAutoModRuleParams",
    "DeleteChannelParams",
    "DeleteEmojiParams",
    "DeleteInviteParams",
    "DeleteRoleParams",
    "DeleteScheduledEventParams",
    "DeleteStickerParams",
    "DeleteWebhookParams",
    "EditAutoModRuleParams",
    "EditChannelParams",
    "EditMemberParams",
    "EditRoleParams",
    "EditScheduledEventParams",
    "EditServerParams",
    "EditWebhookParams",
    "EditWelcomeScreenParams",
    "KickMemberParams",
    "LockThreadParams",
    "RemoveRoleParams",
    "RenameEmojiParams",
    "SetChannelPermissionOverridesParams",
    "SetChannelPermissionsParams",
    "UnarchiveThreadParams",
    "UnbanMemberParams",
    "WelcomeChannelEntry",
]
