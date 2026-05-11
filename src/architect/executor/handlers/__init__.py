"""Handler registry — single source of truth for tool dispatch.

Each entry maps a tool name to ``(handler_callable, params_model,
required_permission)``. ``required_permission`` is ``None`` for read-only
tools. ``Executor.execute`` consumes this table; ``architect.agent.tools``
generates the LLM-facing JSON Schema from the same models.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import discord
from pydantic import BaseModel

from architect.executor.handlers import (
    automod,
    channels,
    emojis,
    events,
    members,
    moderation,
    readonly,
    roles,
    server,
    threads,
)
from architect.executor.handlers import (
    permissions as permissions_handlers,
)
from architect.executor.permissions import REQUIRED_PERMISSIONS

# A handler accepts a validated params model (any subclass of BaseModel) and
# returns a human-readable result string. ``Any`` on params is intentional:
# the registry stores heterogeneous models and the dispatcher validates the
# correct one before invoking the handler.
Handler = Callable[[Any, discord.Guild], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class HandlerSpec:
    handler: Handler
    params_model: type[BaseModel]
    required_permission: str | None


def _spec(handler: Handler, params_model: type[BaseModel], tool_name: str) -> HandlerSpec:
    return HandlerSpec(
        handler=handler,
        params_model=params_model,
        required_permission=REQUIRED_PERMISSIONS.get(tool_name),
    )


# Mutation handlers
_CHANNELS = {
    "create_category": (channels.create_category, channels.CreateCategoryParams),
    "create_text_channel": (channels.create_text_channel, channels.CreateTextChannelParams),
    "create_voice_channel": (channels.create_voice_channel, channels.CreateVoiceChannelParams),
    "create_forum_channel": (channels.create_forum_channel, channels.CreateForumChannelParams),
    "create_stage_channel": (channels.create_stage_channel, channels.CreateStageChannelParams),
    "edit_channel": (channels.edit_channel, channels.EditChannelParams),
    "delete_channel": (channels.delete_channel, channels.DeleteChannelParams),
    "set_channel_permissions": (
        channels.set_channel_permissions,
        channels.SetChannelPermissionsParams,
    ),
    "create_invite": (channels.create_invite, channels.CreateInviteParams),
    "delete_invite": (channels.delete_invite, channels.DeleteInviteParams),
    "create_webhook": (channels.create_webhook, channels.CreateWebhookParams),
    "edit_webhook": (channels.edit_webhook, channels.EditWebhookParams),
    "delete_webhook": (channels.delete_webhook, channels.DeleteWebhookParams),
}

_ROLES = {
    "create_role": (roles.create_role, roles.CreateRoleParams),
    "edit_role": (roles.edit_role, roles.EditRoleParams),
    "delete_role": (roles.delete_role, roles.DeleteRoleParams),
    "assign_role": (roles.assign_role, roles.AssignRoleParams),
    "remove_role": (roles.remove_role, roles.RemoveRoleParams),
}

_MEMBERS = {
    "edit_member": (members.edit_member, members.EditMemberParams),
}

_EVENTS = {
    "create_scheduled_event": (events.create_scheduled_event, events.CreateScheduledEventParams),
    "edit_scheduled_event": (events.edit_scheduled_event, events.EditScheduledEventParams),
    "delete_scheduled_event": (events.delete_scheduled_event, events.DeleteScheduledEventParams),
}

_AUTOMOD = {
    "create_automod_rule": (automod.create_automod_rule, automod.CreateAutoModRuleParams),
    "edit_automod_rule": (automod.edit_automod_rule, automod.EditAutoModRuleParams),
    "delete_automod_rule": (automod.delete_automod_rule, automod.DeleteAutoModRuleParams),
}

_SERVER = {
    "edit_server": (server.edit_server, server.EditServerParams),
    "edit_welcome_screen": (server.edit_welcome_screen, server.EditWelcomeScreenParams),
}

_THREADS = {
    "create_thread": (threads.create_thread, threads.CreateThreadParams),
    "archive_thread": (threads.archive_thread, threads.ArchiveThreadParams),
    "unarchive_thread": (threads.unarchive_thread, threads.UnarchiveThreadParams),
    "lock_thread": (threads.lock_thread, threads.LockThreadParams),
}

_MODERATION = {
    "ban_member": (moderation.ban_member, moderation.BanMemberParams),
    "kick_member": (moderation.kick_member, moderation.KickMemberParams),
    "unban_member": (moderation.unban_member, moderation.UnbanMemberParams),
    "bulk_timeout_members": (
        moderation.bulk_timeout_members,
        moderation.BulkTimeoutMembersParams,
    ),
}

_EMOJIS = {
    "create_emoji": (emojis.create_emoji, emojis.CreateEmojiParams),
    "delete_emoji": (emojis.delete_emoji, emojis.DeleteEmojiParams),
    "rename_emoji": (emojis.rename_emoji, emojis.RenameEmojiParams),
    "delete_sticker": (emojis.delete_sticker, emojis.DeleteStickerParams),
}

_PERMISSIONS = {
    "set_channel_permission_overrides": (
        permissions_handlers.set_channel_permission_overrides,
        permissions_handlers.SetChannelPermissionOverridesParams,
    ),
}

_READONLY: dict[str, tuple[Handler, type[BaseModel]]] = {
    "list_channels": (readonly.list_channels, readonly.NoParams),
    "list_roles": (readonly.list_roles, readonly.NoParams),
    "get_member_roles": (readonly.get_member_roles, readonly.GetMemberRolesParams),
    "get_server_info": (readonly.get_server_info, readonly.NoParams),
    "list_invites": (readonly.list_invites, readonly.NoParams),
    "list_webhooks": (readonly.list_webhooks, readonly.NoParams),
    "list_scheduled_events": (readonly.list_scheduled_events, readonly.NoParams),
    "list_automod_rules": (readonly.list_automod_rules, readonly.NoParams),
    "check_bot_permissions": (readonly.check_bot_permissions, readonly.NoParams),
    "validate_plan": (readonly.validate_plan_handler, readonly.ValidatePlanParams),
    "list_threads": (readonly.list_threads, readonly.ListThreadsParams),
    "list_emojis": (readonly.list_emojis, readonly.NoParams),
    "list_stickers": (readonly.list_stickers, readonly.NoParams),
    "get_audit_log": (readonly.get_audit_log, readonly.GetAuditLogParams),
    "get_permission_chain": (
        readonly.get_permission_chain,
        readonly.GetPermissionChainParams,
    ),
    "simulate_action": (readonly.simulate_action, readonly.SimulateActionParams),
}


HANDLERS: dict[str, HandlerSpec] = {
    name: _spec(handler, model, name)
    for group in (
        _CHANNELS,
        _ROLES,
        _MEMBERS,
        _EVENTS,
        _AUTOMOD,
        _SERVER,
        _THREADS,
        _MODERATION,
        _EMOJIS,
        _PERMISSIONS,
        _READONLY,
    )
    for name, (handler, model) in group.items()
}


__all__ = ["HANDLERS", "Handler", "HandlerSpec"]
