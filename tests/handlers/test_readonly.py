"""Coverage for read-only handler edge cases (empty results, missing data)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from architect.executor.handlers.readonly import (
    GetAuditLogParams,
    GetMemberRolesParams,
    GetPermissionChainParams,
    ListThreadsParams,
    NoParams,
    SimulateActionParams,
    ValidatePlanParams,
    check_bot_permissions,
    get_audit_log,
    get_member_roles,
    get_permission_chain,
    list_automod_rules,
    list_emojis,
    list_invites,
    list_scheduled_events,
    list_stickers,
    list_threads,
    list_webhooks,
    simulate_action,
    validate_plan_handler,
)


def _empty_guild() -> MagicMock:
    guild = MagicMock(spec=discord.Guild)
    guild.invites = AsyncMock(return_value=[])
    guild.webhooks = AsyncMock(return_value=[])
    guild.fetch_automod_rules = AsyncMock(return_value=[])
    guild.scheduled_events = []
    return guild


@pytest.mark.asyncio
async def test_list_invites_empty():
    assert await list_invites(NoParams(), _empty_guild()) == "No active invites."


@pytest.mark.asyncio
async def test_list_webhooks_empty():
    assert await list_webhooks(NoParams(), _empty_guild()) == "No webhooks."


@pytest.mark.asyncio
async def test_list_automod_rules_empty():
    assert await list_automod_rules(NoParams(), _empty_guild()) == "No AutoMod rules."


@pytest.mark.asyncio
async def test_list_scheduled_events_empty():
    assert await list_scheduled_events(NoParams(), _empty_guild()) == "No scheduled events."


@pytest.mark.asyncio
async def test_check_bot_permissions_no_member():
    guild = _empty_guild()
    guild.me = None
    result = await check_bot_permissions(NoParams(), guild)
    assert "membership missing" in result


@pytest.mark.asyncio
async def test_check_bot_permissions_all_granted():
    guild = _empty_guild()
    perms = type("P", (), {})()
    # Set every required permission to True
    for name in [
        "manage_channels",
        "create_instant_invite",
        "manage_webhooks",
        "manage_roles",
        "moderate_members",
        "manage_events",
        "manage_guild",
        "manage_threads",
        "ban_members",
        "kick_members",
        "manage_emojis_and_stickers",
    ]:
        setattr(perms, name, True)
    me = MagicMock()
    me.guild_permissions = perms
    guild.me = me
    result = await check_bot_permissions(NoParams(), guild)
    assert "All required permissions are present" in result


@pytest.mark.asyncio
async def test_get_member_roles_unknown_user_raises():
    guild = MagicMock(spec=discord.Guild)
    guild.get_member = MagicMock(return_value=None)
    with pytest.raises(ValueError, match="Member not found"):
        await get_member_roles(GetMemberRolesParams(user="123"), guild)


@pytest.mark.asyncio
async def test_validate_plan_handler_clean_plan_returns_ok():
    guild = MagicMock(spec=discord.Guild)
    guild.channels = []
    guild.roles = []
    guild.me = None
    params = ValidatePlanParams(
        title="Test",
        actions=[
            {"type": "create_text_channel", "params": {"name": "general"}}
        ],
    )
    result = await validate_plan_handler(params, guild)
    assert "no issues" in result


@pytest.mark.asyncio
async def test_validate_plan_handler_reports_errors():
    guild = MagicMock(spec=discord.Guild)
    guild.channels = []
    guild.roles = []
    guild.me = None
    params = ValidatePlanParams(
        title="Bad",
        actions=[
            {"type": "create_text_channel", "params": {"name": "x"}},
            {"type": "create_text_channel", "params": {"name": "x"}},
        ],
    )
    result = await validate_plan_handler(params, guild)
    assert "❌" in result
    assert "action #2" in result


# ── list_threads ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_threads_empty():
    guild = MagicMock(spec=discord.Guild)
    guild.threads = []
    result = await list_threads(ListThreadsParams(), guild)
    assert "No active threads" in result


@pytest.mark.asyncio
async def test_list_threads_with_threads():
    guild = MagicMock(spec=discord.Guild)
    parent = MagicMock()
    parent.name = "help"
    thread = MagicMock()
    thread.name = "FAQ"
    thread.parent = parent
    thread.locked = False
    thread.archived = False
    thread.member_count = 5
    guild.threads = [thread]
    result = await list_threads(ListThreadsParams(), guild)
    assert "FAQ" in result
    assert "#help" in result
    assert "5 members" in result


@pytest.mark.asyncio
async def test_list_threads_channel_filter():
    guild = MagicMock(spec=discord.Guild)
    parent_a = MagicMock()
    parent_a.name = "help"
    parent_b = MagicMock()
    parent_b.name = "off-topic"
    t1 = MagicMock(name="x")
    t1.name = "FAQ"
    t1.parent = parent_a
    t1.locked = False
    t1.archived = False
    t1.member_count = 1
    t2 = MagicMock()
    t2.name = "Memes"
    t2.parent = parent_b
    t2.locked = False
    t2.archived = False
    t2.member_count = 1
    guild.threads = [t1, t2]
    result = await list_threads(ListThreadsParams(channel="off-topic"), guild)
    assert "Memes" in result
    assert "FAQ" not in result


# ── list_emojis ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_emojis_empty_uses_tier_slots():
    guild = MagicMock(spec=discord.Guild)
    guild.emojis = []
    guild.premium_tier = 2
    result = await list_emojis(NoParams(), guild)
    assert "0/150" in result  # tier 2 = 150 slots


@pytest.mark.asyncio
async def test_list_emojis_with_emojis():
    guild = MagicMock(spec=discord.Guild)
    e1 = MagicMock()
    e1.name = "thinking"
    e1.animated = False
    e2 = MagicMock()
    e2.name = "wave"
    e2.animated = True
    guild.emojis = [e1, e2]
    guild.premium_tier = 0
    result = await list_emojis(NoParams(), guild)
    assert "2/50" in result
    assert ":thinking:" in result
    assert "1 static" in result
    assert "1 animated" in result


# ── list_stickers ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_stickers_empty():
    guild = MagicMock(spec=discord.Guild)
    guild.stickers = []
    guild.premium_tier = 0
    result = await list_stickers(NoParams(), guild)
    assert "0/5" in result


# ── get_audit_log ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_audit_log_unknown_action():
    guild = MagicMock(spec=discord.Guild)
    result = await get_audit_log(
        GetAuditLogParams(limit=10, action_type="bogus_action"), guild
    )
    assert "Unknown audit log action" in result


@pytest.mark.asyncio
async def test_get_audit_log_empty_entries():
    guild = MagicMock(spec=discord.Guild)

    async def _empty(*_args, **_kwargs):
        # async generator yielding nothing
        if False:
            yield None  # pragma: no cover

    guild.audit_logs = _empty
    result = await get_audit_log(GetAuditLogParams(limit=5), guild)
    assert "no matching entries" in result


# ── get_permission_chain ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_permission_chain_unknown_user():
    guild = MagicMock(spec=discord.Guild)
    guild.get_member = MagicMock(return_value=None)
    result = await get_permission_chain(
        GetPermissionChainParams(user="999"), guild
    )
    assert "not found" in result


@pytest.mark.asyncio
async def test_get_permission_chain_no_channel():
    guild = MagicMock(spec=discord.Guild)
    member = MagicMock()
    member.display_name = "Alice"
    member.id = 42
    top_role = MagicMock()
    top_role.name = "Mod"
    top_role.position = 5
    member.top_role = top_role
    everyone = MagicMock()
    everyone.name = "@everyone"
    everyone.position = 0
    mod = MagicMock()
    mod.name = "Mod"
    mod.position = 5
    member.roles = [everyone, mod]
    perms = MagicMock()
    perms.__iter__ = lambda self: iter(
        [("view_channel", True), ("send_messages", True), ("kick_members", False)]
    )
    member.guild_permissions = perms
    guild.get_member = MagicMock(return_value=member)
    result = await get_permission_chain(
        GetPermissionChainParams(user="42"), guild
    )
    assert "Alice" in result
    assert "Mod" in result
    assert "view_channel" in result


# ── simulate_action ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_simulate_action_clean():
    guild = MagicMock(spec=discord.Guild)
    guild.channels = []
    guild.roles = []
    guild.me = None
    result = await simulate_action(
        SimulateActionParams(type="create_text_channel", params={"name": "fresh"}),
        guild,
    )
    assert "no issues" in result


@pytest.mark.asyncio
async def test_simulate_action_reports_issues():
    guild = MagicMock(spec=discord.Guild)

    # existing channel "general" → create with same name should warn/error
    existing = MagicMock()
    existing.name = "general"
    existing.id = 1
    existing.type = discord.ChannelType.text
    existing.position = 0
    existing.category = None
    guild.channels = [existing]
    guild.text_channels = [existing]
    guild.voice_channels = []
    guild.categories = []
    guild.forum_channels = []
    guild.stage_channels = []
    guild.roles = []
    guild.me = None
    result = await simulate_action(
        SimulateActionParams(
            type="create_text_channel", params={"name": "general"}
        ),
        guild,
    )
    # Whether it's an error or a warning depends on the validator's view of
    # duplicate names; either way the result must NOT be the all-clean message.
    assert "no issues" not in result


# ── get_member_roles_filters_everyone (existing) ─────────────────────────────


@pytest.mark.asyncio
async def test_get_member_roles_filters_everyone():
    guild = MagicMock(spec=discord.Guild)
    everyone = MagicMock()
    everyone.name = "@everyone"
    role = MagicMock()
    role.name = "Admin"
    member = MagicMock()
    member.roles = [everyone, role]
    guild.get_member = MagicMock(return_value=member)
    result = await get_member_roles(GetMemberRolesParams(user="123"), guild)
    assert "@everyone" not in result
    assert "Admin" in result
