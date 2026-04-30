"""Channel-domain handlers (text, voice, forum, stage, invites, webhooks)."""

from __future__ import annotations

import discord

from architect.executor._resolve import resolve_category, resolve_channel, resolve_webhook
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


async def create_category(params: CreateCategoryParams, guild: discord.Guild) -> str:
    await guild.create_category(name=params.name)
    return f"Category created: {params.name}"


async def create_text_channel(params: CreateTextChannelParams, guild: discord.Guild) -> str:
    category = resolve_category(guild, params.category)
    await guild.create_text_channel(name=params.name, category=category)
    return f"Text channel created: #{params.name}"


async def create_voice_channel(params: CreateVoiceChannelParams, guild: discord.Guild) -> str:
    category = resolve_category(guild, params.category)
    await guild.create_voice_channel(name=params.name, category=category)
    return f"Voice channel created: {params.name}"


async def create_forum_channel(params: CreateForumChannelParams, guild: discord.Guild) -> str:
    category = resolve_category(guild, params.category)
    kwargs: dict = {"name": params.name}
    if category:
        kwargs["category"] = category
    if params.topic is not None:
        kwargs["topic"] = params.topic
    if params.slowmode is not None:
        kwargs["slowmode_delay"] = params.slowmode
    if params.nsfw is not None:
        kwargs["nsfw"] = params.nsfw
    if params.available_tags:
        kwargs["available_tags"] = [discord.ForumTag(name=t) for t in params.available_tags]
    if params.require_tag is not None:
        kwargs["require_tag"] = params.require_tag
    if params.default_sort_order is not None:
        sort_map = {
            "latest_activity": discord.ForumOrderType.latest_activity,
            "creation_date": discord.ForumOrderType.creation_date,
        }
        kwargs["default_sort_order"] = sort_map[params.default_sort_order]
    if params.default_forum_layout is not None:
        layout_map = {
            "list": discord.ForumLayoutType.list_view,
            "gallery": discord.ForumLayoutType.gallery_view,
        }
        kwargs["default_layout"] = layout_map[params.default_forum_layout]
    await guild.create_forum(**kwargs)
    return f"Forum channel created: #{params.name}"


async def create_stage_channel(params: CreateStageChannelParams, guild: discord.Guild) -> str:
    category = resolve_category(guild, params.category)
    kwargs: dict = {"name": params.name}
    if category:
        kwargs["category"] = category
    if params.bitrate is not None:
        kwargs["bitrate"] = params.bitrate
    if params.user_limit is not None:
        kwargs["user_limit"] = params.user_limit
    if params.rtc_region is not None:
        kwargs["rtc_region"] = params.rtc_region
    if params.position is not None:
        kwargs["position"] = params.position
    await guild.create_stage_channel(**kwargs)
    return f"Stage channel created: {params.name}"


async def edit_channel(params: EditChannelParams, guild: discord.Guild) -> str:
    channel = resolve_channel(guild, params.channel)
    if channel is None:
        raise ValueError(f"Channel not found: {params.channel!r}")
    kwargs: dict = {}
    if params.name is not None:
        kwargs["name"] = params.name
    if params.topic is not None:
        kwargs["topic"] = params.topic
    if params.slowmode is not None:
        kwargs["slowmode_delay"] = params.slowmode
    if params.nsfw is not None:
        kwargs["nsfw"] = params.nsfw
    if params.position is not None:
        kwargs["position"] = params.position
    if params.bitrate is not None:
        kwargs["bitrate"] = params.bitrate
    if params.user_limit is not None:
        kwargs["user_limit"] = params.user_limit
    if params.rtc_region is not None:
        kwargs["rtc_region"] = params.rtc_region
    if params.video_quality_mode is not None:
        kwargs["video_quality_mode"] = discord.VideoQualityMode[params.video_quality_mode]
    if params.parent_id is not None:
        kwargs["category"] = resolve_category(guild, params.parent_id)
    if params.default_auto_archive_duration is not None:
        kwargs["default_auto_archive_duration"] = params.default_auto_archive_duration
    await channel.edit(**kwargs)
    return f"Channel updated: {params.channel}"


async def delete_channel(params: DeleteChannelParams, guild: discord.Guild) -> str:
    channel = resolve_channel(guild, params.channel)
    if channel is None:
        raise ValueError(f"Channel not found: {params.channel!r}")
    rules_ch = getattr(guild, "rules_channel", None)
    if rules_ch is not None and channel.id == rules_ch.id:
        raise ValueError(f"Cannot delete the rules channel: {params.channel!r}")
    await channel.delete(reason=params.reason)
    return f"Channel deleted: {params.channel}"


async def set_channel_permissions(params: SetChannelPermissionsParams, guild: discord.Guild) -> str:
    channel = discord.utils.get(guild.channels, name=params.channel)
    if channel is None:
        raise ValueError(f"Channel not found: {params.channel!r}")
    role = discord.utils.get(guild.roles, name=params.role)
    if role is None:
        raise ValueError(f"Role not found: {params.role!r}")
    overwrite_kwargs: dict[str, bool] = {}
    for perm in params.allow or []:
        overwrite_kwargs[perm] = True
    for perm in params.deny or []:
        overwrite_kwargs[perm] = False
    overwrite = discord.PermissionOverwrite(**overwrite_kwargs)
    await channel.set_permissions(role, overwrite=overwrite)
    return f"Permissions set: #{params.channel} → @{params.role}"


async def create_invite(params: CreateInviteParams, guild: discord.Guild) -> str:
    channel = resolve_channel(guild, params.channel)
    if channel is None:
        raise ValueError(f"Channel not found: {params.channel!r}")
    kwargs: dict = {}
    if params.max_age is not None:
        kwargs["max_age"] = params.max_age
    if params.max_uses is not None:
        kwargs["max_uses"] = params.max_uses
    if params.temporary is not None:
        kwargs["temporary"] = params.temporary
    invite = await channel.create_invite(**kwargs)
    return f"Invite created: {invite.url}"


async def delete_invite(params: DeleteInviteParams, guild: discord.Guild) -> str:
    invites = await guild.invites()
    invite = next((i for i in invites if i.code == params.code), None)
    if invite is None:
        raise ValueError(f"Invite not found: {params.code!r}")
    await invite.delete()
    return f"Invite revoked: {params.code}"


async def create_webhook(params: CreateWebhookParams, guild: discord.Guild) -> str:
    channel = resolve_channel(guild, params.channel)
    if channel is None:
        raise ValueError(f"Channel not found: {params.channel!r}")
    webhook = await channel.create_webhook(name=params.name)
    return f"Webhook created: {webhook.name} in #{params.channel}"


async def edit_webhook(params: EditWebhookParams, guild: discord.Guild) -> str:
    webhook = await resolve_webhook(guild, params.webhook)
    if webhook is None:
        raise ValueError(f"Webhook not found: {params.webhook!r}")
    kwargs: dict = {}
    if params.name is not None:
        kwargs["name"] = params.name
    if params.channel is not None:
        target_ch = resolve_channel(guild, params.channel)
        if target_ch is None:
            raise ValueError(f"Channel not found: {params.channel!r}")
        kwargs["channel"] = target_ch
    await webhook.edit(**kwargs)
    return f"Webhook updated: {params.webhook}"


async def delete_webhook(params: DeleteWebhookParams, guild: discord.Guild) -> str:
    webhook = await resolve_webhook(guild, params.webhook)
    if webhook is None:
        raise ValueError(f"Webhook not found: {params.webhook!r}")
    await webhook.delete()
    return f"Webhook deleted: {params.webhook}"
