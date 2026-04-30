"""AutoMod handlers."""

from __future__ import annotations

from datetime import timedelta

import discord

from architect.executor._resolve import resolve_channel, resolve_role
from architect.models.params.automod import (
    CreateAutoModRuleParams,
    DeleteAutoModRuleParams,
    EditAutoModRuleParams,
)

_TRIGGER_TYPE_MAP = {
    "keyword": discord.AutoModRuleTriggerType.keyword,
    "spam": discord.AutoModRuleTriggerType.spam,
    "keyword_preset": discord.AutoModRuleTriggerType.keyword_preset,
    "mention_spam": discord.AutoModRuleTriggerType.mention_spam,
}

_PRESET_MAP = {
    "profanity": discord.AutoModPresets.profanity,
    "sexual_content": discord.AutoModPresets.sexual_content,
    "slurs": discord.AutoModPresets.slurs,
}

_EVENT_TYPE_MAP = {
    "message_send": discord.AutoModRuleEventType.message_send,
    "member_update": discord.AutoModRuleEventType.member_update,
}


def _build_trigger(params: CreateAutoModRuleParams) -> discord.AutoModTrigger:
    kwargs: dict = {"type": _TRIGGER_TYPE_MAP[params.trigger_type]}
    if params.keyword_filter:
        kwargs["keyword_filter"] = params.keyword_filter
    if params.regex_patterns:
        kwargs["regex_patterns"] = params.regex_patterns
    if params.allow_list:
        kwargs["allow_list"] = params.allow_list
    if params.presets:
        presets = discord.AutoModPresets.none()
        for p in params.presets:
            presets |= _PRESET_MAP[p]
        kwargs["presets"] = presets
    if params.mention_limit is not None:
        kwargs["mention_limit"] = params.mention_limit
    if params.mention_raid_protection is not None:
        kwargs["mention_raid_protection"] = params.mention_raid_protection
    return discord.AutoModTrigger(**kwargs)


def _build_actions(guild: discord.Guild, actions: list[str]) -> list[discord.AutoModRuleAction]:
    result: list[discord.AutoModRuleAction] = []
    for action_str in actions:
        if action_str == "block_message":
            result.append(
                discord.AutoModRuleAction(type=discord.AutoModRuleActionType.block_message)
            )
        elif action_str.startswith("send_alert:"):
            ch_ref = action_str[len("send_alert:") :]
            ch = resolve_channel(guild, ch_ref)
            if ch is None:
                raise ValueError(f"Alert channel not found: {ch_ref!r}")
            result.append(
                discord.AutoModRuleAction(
                    type=discord.AutoModRuleActionType.send_alert_message,
                    channel_id=ch.id,
                )
            )
        elif action_str.startswith("timeout:"):
            duration_seconds = int(action_str[len("timeout:") :])
            result.append(
                discord.AutoModRuleAction(
                    type=discord.AutoModRuleActionType.timeout,
                    duration=timedelta(seconds=duration_seconds),
                )
            )
    return result


async def _find_rule(guild: discord.Guild, ref: str) -> discord.AutoModRule:
    rules = await guild.fetch_auto_moderation_rules()
    rule = next((r for r in rules if str(r.id) == ref or r.name == ref), None)
    if rule is None:
        raise ValueError(f"AutoMod rule not found: {ref!r}")
    return rule


async def create_automod_rule(params: CreateAutoModRuleParams, guild: discord.Guild) -> str:
    trigger = _build_trigger(params)
    actions = _build_actions(guild, params.actions)
    kwargs: dict = {
        "name": params.name,
        "event_type": _EVENT_TYPE_MAP[params.event_type],
        "trigger": trigger,
        "actions": actions,
        "enabled": bool(params.enabled),
    }
    exempt_roles = [resolve_role(guild, r) for r in (params.exempt_roles or [])]
    exempt_channels = [
        c for r in (params.exempt_channels or []) if (c := resolve_channel(guild, r)) is not None
    ]
    if exempt_roles:
        kwargs["exempt_roles"] = [r for r in exempt_roles if r]
    if exempt_channels:
        kwargs["exempt_channels"] = exempt_channels
    rule = await guild.create_automod_rule(**kwargs)
    return f"AutoMod rule created: {rule.name}"


async def edit_automod_rule(params: EditAutoModRuleParams, guild: discord.Guild) -> str:
    rule = await _find_rule(guild, params.rule)
    kwargs: dict = {}
    if params.name is not None:
        kwargs["name"] = params.name
    if params.enabled is not None:
        kwargs["enabled"] = params.enabled
    if params.actions:
        kwargs["actions"] = _build_actions(guild, params.actions)
    if params.exempt_roles is not None:
        kwargs["exempt_roles"] = [r for n in params.exempt_roles if (r := resolve_role(guild, n))]
    if params.exempt_channels is not None:
        kwargs["exempt_channels"] = [
            c for n in params.exempt_channels if (c := resolve_channel(guild, n)) is not None
        ]
    await rule.edit(**kwargs)
    return f"AutoMod rule updated: {params.rule}"


async def delete_automod_rule(params: DeleteAutoModRuleParams, guild: discord.Guild) -> str:
    rule = await _find_rule(guild, params.rule)
    await rule.delete()
    return f"AutoMod rule deleted: {params.rule}"
