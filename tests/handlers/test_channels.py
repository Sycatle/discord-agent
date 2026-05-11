"""Coverage for channel handlers (forum, stage, edit, invites, webhooks)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from architect.executor.handlers.channels import (
    create_forum_channel,
    create_invite,
    create_stage_channel,
    create_webhook,
    delete_channel,
    delete_invite,
    delete_webhook,
    edit_channel,
    edit_webhook,
)
from architect.models.params.channels import (
    CreateForumChannelParams,
    CreateInviteParams,
    CreateStageChannelParams,
    CreateWebhookParams,
    DeleteChannelParams,
    DeleteInviteParams,
    DeleteWebhookParams,
    EditChannelParams,
    EditWebhookParams,
)


def _make_guild() -> MagicMock:
    guild = MagicMock(spec=discord.Guild)
    cat = MagicMock()
    cat.name = "Cat"
    guild.categories = [cat]
    text = MagicMock()
    text.name = "general"
    text.id = 1
    text.edit = AsyncMock()
    text.delete = AsyncMock()
    text.create_invite = AsyncMock(return_value=MagicMock(url="https://discord.gg/abc"))
    text.create_webhook = AsyncMock(return_value=MagicMock(name="WH"))
    guild.channels = [text]
    guild.get_channel = MagicMock(return_value=None)
    guild.rules_channel = None

    wh = MagicMock()
    wh.name = "wh"
    wh.id = 7
    wh.edit = AsyncMock()
    wh.delete = AsyncMock()
    guild.webhooks = AsyncMock(return_value=[wh])

    invite = MagicMock()
    invite.code = "abc123"
    invite.delete = AsyncMock()
    guild.invites = AsyncMock(return_value=[invite])

    forum_mock = MagicMock(name="forum")
    forum_mock.edit = AsyncMock()
    guild.create_forum = AsyncMock(return_value=forum_mock)
    guild.create_stage_channel = AsyncMock(return_value=MagicMock(name="stage"))
    return guild


# ── create_forum_channel ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_forum_with_full_payload():
    guild = _make_guild()
    params = CreateForumChannelParams(
        name="discussion",
        category="Cat",
        topic="Welcome",
        slowmode=10,
        nsfw=False,
        available_tags=["help", "bug"],
        require_tag=True,
        default_sort_order="latest_activity",
        default_forum_layout="gallery",
    )
    result = await create_forum_channel(params, guild)
    assert result == "Forum channel created: #discussion"
    kwargs = guild.create_forum.call_args.kwargs
    assert kwargs["name"] == "discussion"
    assert kwargs["slowmode_delay"] == 10
    # require_tag isn't supported by Guild.create_forum — applied via ForumChannel.edit afterwards
    assert "require_tag" not in kwargs
    forum = guild.create_forum.return_value
    forum.edit.assert_awaited_once_with(require_tag=True)


@pytest.mark.asyncio
async def test_create_forum_minimal_payload():
    guild = _make_guild()
    await create_forum_channel(CreateForumChannelParams(name="f"), guild)
    guild.create_forum.assert_called_once()


# ── create_stage_channel ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_stage_with_full_payload():
    guild = _make_guild()
    params = CreateStageChannelParams(
        name="stage",
        category="Cat",
        bitrate=64000,
        user_limit=50,
        rtc_region="us-east",
        position=1,
    )
    await create_stage_channel(params, guild)
    kwargs = guild.create_stage_channel.call_args.kwargs
    assert kwargs["bitrate"] == 64000
    assert kwargs["user_limit"] == 50


# ── edit_channel ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_channel_unknown_target_raises():
    guild = _make_guild()
    with pytest.raises(ValueError, match="Channel not found"):
        await edit_channel(EditChannelParams(channel="ghost"), guild)


@pytest.mark.asyncio
async def test_edit_channel_full_payload():
    guild = _make_guild()
    params = EditChannelParams(
        channel="general",
        name="renamed",
        topic="topic",
        slowmode=15,
        nsfw=True,
        position=2,
        bitrate=64000,
        user_limit=10,
        rtc_region="eu-west",
        video_quality_mode="full",
        parent_id="Cat",
        default_auto_archive_duration=1440,
    )
    await edit_channel(params, guild)
    edit = guild.channels[0].edit
    edit.assert_called_once()
    kwargs = edit.call_args.kwargs
    assert kwargs["name"] == "renamed"
    assert kwargs["slowmode_delay"] == 15
    assert kwargs["video_quality_mode"] == discord.VideoQualityMode.full


# ── delete_channel ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_channel_unknown_raises():
    guild = _make_guild()
    with pytest.raises(ValueError, match="Channel not found"):
        await delete_channel(DeleteChannelParams(channel="ghost"), guild)


@pytest.mark.asyncio
async def test_delete_channel_refuses_rules_channel():
    guild = _make_guild()
    rules = MagicMock()
    rules.id = 1
    guild.rules_channel = rules
    with pytest.raises(ValueError, match="Cannot delete the rules channel"):
        await delete_channel(DeleteChannelParams(channel="general"), guild)


@pytest.mark.asyncio
async def test_delete_channel_passes_reason():
    guild = _make_guild()
    await delete_channel(DeleteChannelParams(channel="general", reason="cleanup"), guild)
    guild.channels[0].delete.assert_called_once_with(reason="cleanup")


# ── invites ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_invite_unknown_channel_raises():
    guild = _make_guild()
    with pytest.raises(ValueError, match="Channel not found"):
        await create_invite(CreateInviteParams(channel="ghost"), guild)


@pytest.mark.asyncio
async def test_create_invite_with_options():
    guild = _make_guild()
    params = CreateInviteParams(channel="general", max_age=3600, max_uses=10, temporary=True)
    result = await create_invite(params, guild)
    assert "discord.gg/abc" in result


@pytest.mark.asyncio
async def test_delete_invite_unknown_raises():
    guild = _make_guild()
    with pytest.raises(ValueError, match="Invite not found"):
        await delete_invite(DeleteInviteParams(code="zzz"), guild)


@pytest.mark.asyncio
async def test_delete_invite_revokes():
    guild = _make_guild()
    await delete_invite(DeleteInviteParams(code="abc123"), guild)
    (await guild.invites())[0].delete.assert_called_once()


# ── webhooks ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_webhook_unknown_channel_raises():
    guild = _make_guild()
    with pytest.raises(ValueError, match="Channel not found"):
        await create_webhook(CreateWebhookParams(channel="ghost", name="wh"), guild)


@pytest.mark.asyncio
async def test_edit_webhook_unknown_raises():
    guild = _make_guild()
    guild.webhooks = AsyncMock(return_value=[])
    with pytest.raises(ValueError, match="Webhook not found"):
        await edit_webhook(EditWebhookParams(webhook="ghost"), guild)


@pytest.mark.asyncio
async def test_edit_webhook_unknown_target_channel_raises():
    guild = _make_guild()
    with pytest.raises(ValueError, match="Channel not found"):
        await edit_webhook(EditWebhookParams(webhook="wh", channel="ghost"), guild)


@pytest.mark.asyncio
async def test_edit_webhook_renames_and_moves():
    guild = _make_guild()
    await edit_webhook(EditWebhookParams(webhook="wh", name="renamed", channel="general"), guild)
    wh = (await guild.webhooks())[0]
    wh.edit.assert_called_once()
    kwargs = wh.edit.call_args.kwargs
    assert kwargs["name"] == "renamed"


@pytest.mark.asyncio
async def test_delete_webhook_unknown_raises():
    guild = _make_guild()
    guild.webhooks = AsyncMock(return_value=[])
    with pytest.raises(ValueError, match="Webhook not found"):
        await delete_webhook(DeleteWebhookParams(webhook="ghost"), guild)


@pytest.mark.asyncio
async def test_delete_webhook_deletes():
    guild = _make_guild()
    wh = (await guild.webhooks())[0]
    await delete_webhook(DeleteWebhookParams(webhook="wh"), guild)
    wh.delete.assert_called_once()
