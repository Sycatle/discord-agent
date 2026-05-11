"""Coverage for AutoMod handlers (trigger building, action encoding)."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from architect.executor.handlers.automod import (
    _build_actions,
    _build_trigger,
    create_automod_rule,
    delete_automod_rule,
    edit_automod_rule,
)
from architect.models.params.automod import (
    CreateAutoModRuleParams,
    DeleteAutoModRuleParams,
    EditAutoModRuleParams,
)


def _make_guild() -> MagicMock:
    guild = MagicMock(spec=discord.Guild)
    alert_ch = MagicMock()
    alert_ch.name = "mod-log"
    alert_ch.id = 42
    guild.channels = [alert_ch]
    guild.get_channel = MagicMock(return_value=None)

    role = MagicMock()
    role.name = "VIP"
    role.id = 100
    guild.roles = [role]
    guild.get_role = MagicMock(return_value=None)
    guild.default_role = MagicMock()
    guild.default_role.name = "@everyone"

    rule = MagicMock()
    rule.name = "no-spam"
    rule.id = 999
    rule.edit = AsyncMock()
    rule.delete = AsyncMock()
    guild.fetch_automod_rules = AsyncMock(return_value=[rule])

    created = MagicMock()
    created.name = "no-spam"
    guild.create_automod_rule = AsyncMock(return_value=created)
    return guild


# ── _build_trigger ──────────────────────────────────────────────────────────


def test_build_trigger_keyword_with_filter_and_regex_and_allow_list():
    params = CreateAutoModRuleParams(
        name="r",
        event_type="message_send",
        trigger_type="keyword",
        keyword_filter=["spam"],
        regex_patterns=[r"\bspam\b"],
        allow_list=["okay"],
        actions=["block_message"],
    )
    trigger = _build_trigger(params)
    assert trigger.type == discord.AutoModRuleTriggerType.keyword


def test_build_trigger_keyword_preset_combines_flags():
    params = CreateAutoModRuleParams(
        name="r",
        event_type="message_send",
        trigger_type="keyword_preset",
        presets=["profanity", "slurs"],
        actions=["block_message"],
    )
    trigger = _build_trigger(params)
    assert trigger.type == discord.AutoModRuleTriggerType.keyword_preset


def test_build_trigger_mention_spam_with_limits():
    params = CreateAutoModRuleParams(
        name="r",
        event_type="message_send",
        trigger_type="mention_spam",
        mention_limit=5,
        mention_raid_protection=True,
        actions=["block_message"],
    )
    trigger = _build_trigger(params)
    assert trigger.type == discord.AutoModRuleTriggerType.mention_spam


# ── _build_actions ──────────────────────────────────────────────────────────


def test_build_actions_block_only():
    guild = _make_guild()
    actions = _build_actions(guild, ["block_message"])
    assert len(actions) == 1
    assert actions[0].type == discord.AutoModRuleActionType.block_message


def test_build_actions_send_alert_resolves_channel():
    guild = _make_guild()
    actions = _build_actions(guild, ["send_alert:mod-log"])
    assert actions[0].type == discord.AutoModRuleActionType.send_alert_message
    assert actions[0].channel_id == 42


def test_build_actions_send_alert_unknown_channel_raises():
    guild = _make_guild()
    with pytest.raises(ValueError, match="Alert channel not found"):
        _build_actions(guild, ["send_alert:ghost"])


def test_build_actions_timeout_uses_seconds():
    guild = _make_guild()
    actions = _build_actions(guild, ["timeout:300"])
    assert actions[0].type == discord.AutoModRuleActionType.timeout
    assert actions[0].duration == timedelta(seconds=300)


def test_build_actions_unknown_action_silently_ignored():
    guild = _make_guild()
    actions = _build_actions(guild, ["unknown_action", "block_message"])
    assert len(actions) == 1


# ── create / edit / delete ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_automod_rule_with_exempt_lists():
    guild = _make_guild()
    params = CreateAutoModRuleParams(
        name="no-spam",
        event_type="message_send",
        trigger_type="keyword",
        keyword_filter=["bad"],
        actions=["block_message"],
        exempt_roles=["VIP"],
        exempt_channels=["mod-log"],
    )
    result = await create_automod_rule(params, guild)
    assert "AutoMod rule created" in result
    kwargs = guild.create_automod_rule.call_args.kwargs
    assert len(kwargs["exempt_roles"]) == 1
    assert len(kwargs["exempt_channels"]) == 1


@pytest.mark.asyncio
async def test_edit_automod_rule_full_payload():
    guild = _make_guild()
    params = EditAutoModRuleParams(
        rule="no-spam",
        name="renamed",
        enabled=True,
        actions=["block_message"],
        exempt_roles=["VIP"],
        exempt_channels=["mod-log"],
    )
    result = await edit_automod_rule(params, guild)
    assert "AutoMod rule updated" in result


@pytest.mark.asyncio
async def test_edit_automod_rule_unknown_raises():
    guild = _make_guild()
    guild.fetch_automod_rules = AsyncMock(return_value=[])
    with pytest.raises(ValueError, match="AutoMod rule not found"):
        await edit_automod_rule(EditAutoModRuleParams(rule="ghost"), guild)


@pytest.mark.asyncio
async def test_delete_automod_rule():
    guild = _make_guild()
    rule = (await guild.fetch_automod_rules())[0]
    await delete_automod_rule(DeleteAutoModRuleParams(rule="no-spam"), guild)
    rule.delete.assert_called_once()
