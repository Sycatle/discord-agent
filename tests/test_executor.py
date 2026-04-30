from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from architect.executor.executor import Executor


def _make_guild():
    guild = MagicMock()

    cat = MagicMock()
    cat.name = "Gaming"

    ch_text = MagicMock()
    ch_text.name = "general"

    ch_voice = MagicMock()
    ch_voice.name = "Vocal"

    role_admin = MagicMock()
    role_admin.name = "Admin"

    role_everyone = MagicMock()
    role_everyone.name = "@everyone"

    guild.categories = [cat]
    guild.text_channels = [ch_text]
    guild.voice_channels = [ch_voice]
    guild.channels = [ch_text, ch_voice]
    guild.roles = [role_admin, role_everyone]

    created_category = MagicMock()
    created_category.name = "NewCat"
    guild.create_category = AsyncMock(return_value=created_category)

    created_text = MagicMock()
    created_text.name = "new-channel"
    guild.create_text_channel = AsyncMock(return_value=created_text)

    created_voice = MagicMock()
    created_voice.name = "New Voice"
    guild.create_voice_channel = AsyncMock(return_value=created_voice)

    created_role = MagicMock()
    created_role.name = "Moderator"
    guild.create_role = AsyncMock(return_value=created_role)

    ch_text.set_permissions = AsyncMock()

    return guild


@pytest.mark.asyncio
async def test_create_category():
    guild = _make_guild()
    executor = Executor()
    result = await executor.execute("create_category", {"name": "NewCat"}, guild)
    guild.create_category.assert_called_once_with(name="NewCat")
    assert result == "Category created: NewCat"


@pytest.mark.asyncio
async def test_create_text_channel():
    guild = _make_guild()
    executor = Executor()
    result = await executor.execute("create_text_channel", {"name": "new-channel"}, guild)
    guild.create_text_channel.assert_called_once_with(name="new-channel", category=None)
    assert result == "Text channel created: #new-channel"


@pytest.mark.asyncio
async def test_create_text_channel_with_category():
    guild = _make_guild()
    executor = Executor()

    import discord

    with patch.object(discord.utils, "get", return_value=guild.categories[0]):
        result = await executor.execute(
            "create_text_channel",
            {"name": "news", "category": "Gaming"},
            guild,
        )
    guild.create_text_channel.assert_called_once_with(name="news", category=guild.categories[0])
    assert result == "Text channel created: #news"


@pytest.mark.asyncio
async def test_create_voice_channel():
    guild = _make_guild()
    executor = Executor()
    result = await executor.execute("create_voice_channel", {"name": "New Voice"}, guild)
    guild.create_voice_channel.assert_called_once_with(name="New Voice", category=None)
    assert result == "Voice channel created: New Voice"


@pytest.mark.asyncio
async def test_create_role_with_hex_color():
    guild = _make_guild()
    executor = Executor()

    import discord

    result = await executor.execute(
        "create_role",
        {"name": "Moderator", "color": "#ff0000", "mentionable": True},
        guild,
    )
    guild.create_role.assert_called_once_with(
        name="Moderator",
        color=discord.Color(0xFF0000),
        mentionable=True,
    )
    assert result == "Role created: @Moderator"


@pytest.mark.asyncio
async def test_create_role_with_int_color():
    guild = _make_guild()
    executor = Executor()

    import discord

    result = await executor.execute(
        "create_role",
        {"name": "Member", "color": 0x00FF00},
        guild,
    )
    guild.create_role.assert_called_once_with(
        name="Member",
        color=discord.Color(0x00FF00),
        mentionable=False,
    )
    assert result == "Role created: @Member"


@pytest.mark.asyncio
async def test_set_channel_permissions():
    guild = _make_guild()
    executor = Executor()

    import discord

    ch_text = guild.text_channels[0]
    role_admin = guild.roles[0]

    with patch.object(discord.utils, "get", side_effect=[ch_text, role_admin]):
        result = await executor.execute(
            "set_channel_permissions",
            {
                "channel": "general",
                "role": "Admin",
                "overwrite": {"read_messages": True, "send_messages": False},
            },
            guild,
        )

    ch_text.set_permissions.assert_called_once()
    assert result == "Permissions set: #general → @Admin"


@pytest.mark.asyncio
async def test_list_channels():
    guild = _make_guild()
    executor = Executor()
    result = await executor.execute("list_channels", {}, guild)
    assert "Categories: Gaming" in result
    assert "Text channels: #general" in result
    assert "Voice channels: Vocal" in result


@pytest.mark.asyncio
async def test_list_roles_excludes_everyone():
    guild = _make_guild()
    executor = Executor()
    result = await executor.execute("list_roles", {}, guild)
    assert "Admin" in result
    assert "@everyone" not in result
    assert result.startswith("Roles:")


@pytest.mark.asyncio
async def test_unknown_tool_raises():
    guild = _make_guild()
    executor = Executor()
    with pytest.raises(NotImplementedError, match="No handler for tool"):
        await executor.execute("delete_everything", {}, guild)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _extend_guild(guild):
    """Étend le mock guild avec les méthodes/attributs nécessaires aux nouveaux tests."""
    # Forum channel
    forum_ch = MagicMock()
    forum_ch.name = "annonces-forum"
    guild.create_forum = AsyncMock(return_value=forum_ch)

    # Stage channel
    stage_ch = MagicMock()
    stage_ch.name = "grand-stage"
    guild.create_stage_channel = AsyncMock(return_value=stage_ch)

    # Editable channel mock
    edit_ch = MagicMock()
    edit_ch.name = "general"
    edit_ch.edit = AsyncMock()
    edit_ch.delete = AsyncMock()

    # Invite
    invite = MagicMock()
    invite.url = "https://discord.gg/abc123"
    edit_ch.create_invite = AsyncMock(return_value=invite)

    guild.channels = [edit_ch, guild.channels[0], guild.channels[1]]
    guild.get_channel = MagicMock(return_value=None)  # force name-based lookup

    # default_role (for @everyone guard) — must be the same object as guild.roles[1]
    guild.default_role = guild.roles[1]  # reuse role_everyone from _make_guild()

    existing_role = guild.roles[0]  # "Admin"
    existing_role.id = 222
    existing_role.edit = AsyncMock()
    existing_role.delete = AsyncMock()

    # Member
    member = MagicMock()
    member.id = 999
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()
    member.edit = AsyncMock()
    guild.get_member = MagicMock(return_value=member)

    # Webhooks
    wh = MagicMock()
    wh.name = "mon-webhook"
    wh.id = 777
    wh.edit = AsyncMock()
    wh.delete = AsyncMock()
    guild.webhooks = AsyncMock(return_value=[wh])
    edit_ch.create_webhook = AsyncMock(return_value=wh)

    # Scheduled events
    evt = MagicMock()
    evt.name = "Game Night"
    evt.id = 888
    evt.edit = AsyncMock()
    evt.delete = AsyncMock()
    guild.scheduled_events = [evt]
    guild.create_scheduled_event = AsyncMock(return_value=evt)

    # AutoMod
    rule = MagicMock()
    rule.name = "no-spam"
    rule.id = 555
    rule.enabled = True
    rule.edit = AsyncMock()
    rule.delete = AsyncMock()
    guild.fetch_auto_moderation_rules = AsyncMock(return_value=[rule])
    guild.create_automod_rule = AsyncMock(return_value=rule)

    # guild.edit
    guild.edit = AsyncMock()

    # guild.edit_welcome_screen
    guild.edit_welcome_screen = AsyncMock()

    # invites
    existing_invite = MagicMock()
    existing_invite.code = "xKy3h2"
    existing_invite.delete = AsyncMock()
    guild.invites = AsyncMock(return_value=[existing_invite])

    return guild, edit_ch, member, wh, evt, rule, existing_invite


@pytest.mark.asyncio
async def test_create_forum_channel():
    guild = _make_guild()
    guild, *_ = _extend_guild(guild)
    executor = Executor()
    result = await executor.execute(
        "create_forum_channel",
        {"name": "annonces-forum", "topic": "Annonces importantes"},
        guild,
    )
    guild.create_forum.assert_called_once()
    assert "annonces-forum" in result


@pytest.mark.asyncio
async def test_create_stage_channel():
    guild = _make_guild()
    guild, *_ = _extend_guild(guild)
    executor = Executor()
    result = await executor.execute(
        "create_stage_channel",
        {"name": "grand-stage", "bitrate": 64000},
        guild,
    )
    guild.create_stage_channel.assert_called_once()
    assert "grand-stage" in result


@pytest.mark.asyncio
async def test_edit_channel_rename():
    guild = _make_guild()
    guild, edit_ch, *_ = _extend_guild(guild)
    executor = Executor()
    result = await executor.execute(
        "edit_channel",
        {"channel": "general", "name": "général", "slowmode": 5},
        guild,
    )
    edit_ch.edit.assert_called_once()
    call_kwargs = edit_ch.edit.call_args.kwargs
    assert call_kwargs["name"] == "général"
    assert call_kwargs["slowmode_delay"] == 5
    assert "general" in result


@pytest.mark.asyncio
async def test_edit_channel_not_found():
    guild = _make_guild()
    guild.channels = []
    guild.get_channel = MagicMock(return_value=None)
    guild.default_role = MagicMock()
    executor = Executor()
    with pytest.raises(ValueError, match="Channel not found"):
        await executor.execute("edit_channel", {"channel": "inexistant"}, guild)


@pytest.mark.asyncio
async def test_delete_channel():
    guild = _make_guild()
    guild, edit_ch, *_ = _extend_guild(guild)
    guild.rules_channel = None
    executor = Executor()
    result = await executor.execute(
        "delete_channel",
        {"channel": "general", "reason": "nettoyage"},
        guild,
    )
    edit_ch.delete.assert_called_once_with(reason="nettoyage")
    assert "general" in result


@pytest.mark.asyncio
async def test_delete_channel_guards_rules_channel():
    guild = _make_guild()
    guild, edit_ch, *_ = _extend_guild(guild)
    guild.rules_channel = edit_ch  # edit_ch IS the rules channel
    executor = Executor()
    with pytest.raises(ValueError, match="rules"):
        await executor.execute("delete_channel", {"channel": "general"}, guild)


# ── Domain 2 — Roles ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_role():
    guild = _make_guild()
    guild, *_ = _extend_guild(guild)
    import discord

    executor = Executor()
    result = await executor.execute(
        "edit_role",
        {"role": "Admin", "color": "#FF0000", "hoist": True},
        guild,
    )
    guild.roles[0].edit.assert_called_once()
    call_kwargs = guild.roles[0].edit.call_args.kwargs
    assert call_kwargs["color"] == discord.Color(0xFF0000)
    assert call_kwargs["hoist"] is True
    assert "Admin" in result


@pytest.mark.asyncio
async def test_edit_role_rejects_everyone():
    guild = _make_guild()
    guild, *_ = _extend_guild(guild)
    executor = Executor()
    with pytest.raises(ValueError, match="everyone"):
        await executor.execute("edit_role", {"role": "@everyone"}, guild)


@pytest.mark.asyncio
async def test_delete_role():
    guild = _make_guild()
    guild, *_ = _extend_guild(guild)
    executor = Executor()
    result = await executor.execute("delete_role", {"role": "Admin"}, guild)
    guild.roles[0].delete.assert_called_once()
    assert "Admin" in result


@pytest.mark.asyncio
async def test_assign_role():
    guild = _make_guild()
    guild, _, member, *_ = _extend_guild(guild)
    executor = Executor()
    result = await executor.execute("assign_role", {"user": "<@999>", "role": "Admin"}, guild)
    member.add_roles.assert_called_once_with(guild.roles[0])
    assert "Admin" in result


@pytest.mark.asyncio
async def test_remove_role():
    guild = _make_guild()
    guild, _, member, *_ = _extend_guild(guild)
    executor = Executor()
    result = await executor.execute("remove_role", {"user": "999", "role": "Admin"}, guild)
    member.remove_roles.assert_called_once_with(guild.roles[0])
    assert "Admin" in result


# ── Domain 3 — Members ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_member_nick():
    guild = _make_guild()
    guild, _, member, *_ = _extend_guild(guild)
    executor = Executor()
    result = await executor.execute("edit_member", {"user": "<@999>", "nick": "SuperAdmin"}, guild)
    member.edit.assert_called_once()
    assert member.edit.call_args.kwargs["nick"] == "SuperAdmin"
    assert "999" in result


@pytest.mark.asyncio
async def test_edit_member_timeout():
    guild = _make_guild()
    guild, _, member, *_ = _extend_guild(guild)
    executor = Executor()
    result = await executor.execute(
        "edit_member",
        {"user": "999", "timeout_until": "2026-05-01T12:00:00"},
        guild,
    )
    member.edit.assert_called_once()
    dt = member.edit.call_args.kwargs["communication_disabled_until"]
    assert dt.year == 2026 and dt.month == 5
    assert "999" in result


# ── Domain 4 — Scheduled Events ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_scheduled_event_voice():
    guild = _make_guild()
    guild, edit_ch, *_ = _extend_guild(guild)
    executor = Executor()
    result = await executor.execute(
        "create_scheduled_event",
        {
            "name": "Game Night",
            "start_time": "2026-05-10T20:00:00",
            "entity_type": "voice",
            "channel": "general",
        },
        guild,
    )
    guild.create_scheduled_event.assert_called_once()
    assert "Game Night" in result


@pytest.mark.asyncio
async def test_delete_scheduled_event():
    guild = _make_guild()
    guild, _, _, _, evt, *_ = _extend_guild(guild)
    executor = Executor()
    result = await executor.execute("delete_scheduled_event", {"event": "Game Night"}, guild)
    evt.delete.assert_called_once()
    assert "Game Night" in result


# ── Domain 5 — AutoMod ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_automod_rule_keyword():
    guild = _make_guild()
    guild, *_ = _extend_guild(guild)
    executor = Executor()
    result = await executor.execute(
        "create_automod_rule",
        {
            "name": "no-spam",
            "event_type": "message_send",
            "trigger_type": "keyword",
            "keyword_filter": ["spam", "publicité"],
            "actions": ["block_message"],
        },
        guild,
    )
    guild.create_automod_rule.assert_called_once()
    assert "no-spam" in result


@pytest.mark.asyncio
async def test_delete_automod_rule():
    guild = _make_guild()
    guild, _, _, _, _, rule, _ = _extend_guild(guild)
    executor = Executor()
    result = await executor.execute("delete_automod_rule", {"rule": "no-spam"}, guild)
    rule.delete.assert_called_once()
    assert "no-spam" in result


# ── Domain 6 — Server Settings ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_server_verification_level():
    guild = _make_guild()
    guild, *_ = _extend_guild(guild)
    import discord

    executor = Executor()
    result = await executor.execute("edit_server", {"verification_level": "medium"}, guild)
    guild.edit.assert_called_once_with(verification_level=discord.VerificationLevel.medium)
    assert result == "Server settings updated"


@pytest.mark.asyncio
async def test_edit_server_name_and_locale():
    guild = _make_guild()
    guild, *_ = _extend_guild(guild)
    import discord

    executor = Executor()
    await executor.execute("edit_server", {"name": "Mon Serveur", "preferred_locale": "fr"}, guild)
    call_kwargs = guild.edit.call_args.kwargs
    assert call_kwargs["name"] == "Mon Serveur"
    assert call_kwargs["preferred_locale"] == discord.Locale.french


# ── Read-only ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_member_roles():
    guild = _make_guild()
    guild, _, member, *_ = _extend_guild(guild)
    role_mock = MagicMock()
    role_mock.name = "Admin"
    member.roles = [role_mock]
    executor = Executor()
    result = await executor.execute("get_member_roles", {"user": "<@999>"}, guild)
    assert "Admin" in result


@pytest.mark.asyncio
async def test_list_invites():
    guild = _make_guild()
    guild, _, _, _, _, _, inv = _extend_guild(guild)
    inv.channel = MagicMock()
    inv.channel.name = "general"
    inv.uses = 3
    inv.max_uses = 10
    executor = Executor()
    result = await executor.execute("list_invites", {}, guild)
    assert "xKy3h2" in result


@pytest.mark.asyncio
async def test_list_webhooks():
    guild = _make_guild()
    guild, _, _, wh, *_ = _extend_guild(guild)
    wh.channel = MagicMock()
    wh.channel.name = "general"
    executor = Executor()
    result = await executor.execute("list_webhooks", {}, guild)
    assert "mon-webhook" in result


@pytest.mark.asyncio
async def test_list_scheduled_events():
    guild = _make_guild()
    guild, _, _, _, evt, *_ = _extend_guild(guild)
    evt.entity_type = "voice"
    evt.start_time = "2026-05-10T20:00:00"
    executor = Executor()
    result = await executor.execute("list_scheduled_events", {}, guild)
    assert "Game Night" in result


@pytest.mark.asyncio
async def test_list_automod_rules():
    guild = _make_guild()
    guild, *_ = _extend_guild(guild)
    executor = Executor()
    result = await executor.execute("list_automod_rules", {}, guild)
    assert "no-spam" in result


# ── Invites + Webhooks ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_invite():
    guild = _make_guild()
    guild, edit_ch, *_ = _extend_guild(guild)
    executor = Executor()
    result = await executor.execute(
        "create_invite",
        {"channel": "general", "max_age": 3600, "max_uses": 10},
        guild,
    )
    edit_ch.create_invite.assert_called_once_with(max_age=3600, max_uses=10)
    assert "discord.gg" in result


@pytest.mark.asyncio
async def test_delete_invite():
    guild = _make_guild()
    guild, _, _, _, _, _, inv = _extend_guild(guild)
    executor = Executor()
    result = await executor.execute("delete_invite", {"code": "xKy3h2"}, guild)
    inv.delete.assert_called_once()
    assert "xKy3h2" in result


@pytest.mark.asyncio
async def test_create_webhook():
    guild = _make_guild()
    guild, edit_ch, _, wh, *_ = _extend_guild(guild)
    executor = Executor()
    result = await executor.execute(
        "create_webhook", {"channel": "general", "name": "mon-webhook"}, guild
    )
    edit_ch.create_webhook.assert_called_once_with(name="mon-webhook")
    assert "mon-webhook" in result


@pytest.mark.asyncio
async def test_delete_webhook():
    guild = _make_guild()
    guild, _, _, wh, *_ = _extend_guild(guild)
    executor = Executor()
    result = await executor.execute("delete_webhook", {"webhook": "mon-webhook"}, guild)
    wh.delete.assert_called_once()
    assert "mon-webhook" in result


@pytest.mark.asyncio
async def test_edit_webhook():
    guild = _make_guild()
    guild, _, _, wh, *_ = _extend_guild(guild)
    executor = Executor()
    result = await executor.execute(
        "edit_webhook", {"webhook": "mon-webhook", "name": "new-name"}, guild
    )
    wh.edit.assert_called_once_with(name="new-name")
    assert "mon-webhook" in result


# ── Scheduled Events — Stage & External ──────────────────────────────────────


@pytest.mark.asyncio
async def test_create_scheduled_event_stage():
    guild = _make_guild()
    guild, _, _, _, evt, *_ = _extend_guild(guild)

    # Add a stage channel to guild.channels
    stage_ch = MagicMock()
    stage_ch.name = "stage-channel"
    guild.channels = [stage_ch, *list(guild.channels)]

    evt.name = "Grand Concert"
    executor = Executor()
    result = await executor.execute(
        "create_scheduled_event",
        {
            "name": "Grand Concert",
            "start_time": "2026-06-01T19:00:00",
            "entity_type": "stage",
            "channel": "stage-channel",
        },
        guild,
    )
    guild.create_scheduled_event.assert_called_once()
    call_kwargs = guild.create_scheduled_event.call_args.kwargs
    import discord

    assert call_kwargs["entity_type"] == discord.EntityType.stage_instance
    assert call_kwargs["channel"] is stage_ch
    assert "Grand Concert" in result


@pytest.mark.asyncio
async def test_create_scheduled_event_external():
    guild = _make_guild()
    guild, _, _, _, evt, *_ = _extend_guild(guild)

    evt.name = "Paris Meetup"
    executor = Executor()
    result = await executor.execute(
        "create_scheduled_event",
        {
            "name": "Paris Meetup",
            "start_time": "2026-06-01T18:00:00Z",
            "end_time": "2026-06-01T20:00:00Z",
            "entity_type": "external",
            "location": "Paris",
        },
        guild,
    )
    guild.create_scheduled_event.assert_called_once()
    call_kwargs = guild.create_scheduled_event.call_args.kwargs
    import discord

    assert call_kwargs["entity_type"] == discord.EntityType.external
    assert call_kwargs["location"] == "Paris"
    assert call_kwargs["end_time"] is not None
    assert "Paris Meetup" in result


# ── edit_member voice ops ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_member_voice_ops():
    guild = _make_guild()
    guild, edit_ch, member, *_ = _extend_guild(guild)
    # Add a voice channel named "general-voice"
    voice_ch = MagicMock()
    voice_ch.name = "general-voice"
    guild.channels = [voice_ch, *list(guild.channels)]

    executor = Executor()
    result = await executor.execute(
        "edit_member",
        {"user": "999", "mute": True, "deaf": False, "move_to_channel": "general-voice"},
        guild,
    )
    member.edit.assert_called_once()
    call_kwargs = member.edit.call_args.kwargs
    assert call_kwargs["mute"] is True
    assert call_kwargs["deafen"] is False
    assert call_kwargs["voice_channel"] is voice_ch
    assert "999" in result


# ── check_bot_permissions + strict mode ──────────────────────────────────────


@pytest.mark.asyncio
async def test_check_bot_permissions_lists_granted_and_missing():
    guild = _make_guild()
    me = MagicMock()
    perms = MagicMock()
    perms.manage_channels = True
    perms.manage_roles = True
    perms.manage_webhooks = False
    perms.manage_guild = False
    perms.manage_events = True
    perms.create_instant_invite = True
    perms.moderate_members = False
    me.guild_permissions = perms
    guild.me = me

    executor = Executor()
    result = await executor.execute("check_bot_permissions", {}, guild)
    assert "manage_channels" in result
    assert "manage_webhooks" in result
    assert "manquantes" in result.lower()


@pytest.mark.asyncio
async def test_strict_mode_raises_on_missing_permission():
    from architect.executor.executor import ExecuteError

    guild = _make_guild()
    me = MagicMock()
    perms = MagicMock()
    perms.manage_channels = False
    me.guild_permissions = perms
    guild.me = me

    executor = Executor()
    with pytest.raises(ExecuteError, match="manage_channels"):
        await executor.execute("create_category", {"name": "X"}, guild, strict=True)


@pytest.mark.asyncio
async def test_non_strict_returns_error_string_on_missing_permission():
    guild = _make_guild()
    me = MagicMock()
    perms = MagicMock()
    perms.manage_channels = False
    me.guild_permissions = perms
    guild.me = me

    executor = Executor()
    result = await executor.execute("create_category", {"name": "X"}, guild)
    assert "Permission manquante" in result
