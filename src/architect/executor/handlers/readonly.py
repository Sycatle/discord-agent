"""Read-only handlers (no mutations).

These are dispatched without permission checks (they don't mutate state)
and accept either a typed Pydantic model or no params at all. They share
the same signature as mutation handlers so the registry stays uniform.
"""

from __future__ import annotations

import discord
from pydantic import BaseModel, ConfigDict, Field

from architect.executor._resolve import parse_member
from architect.executor.permissions import REQUIRED_PERMISSIONS
from architect.executor.validator import validate_plan

# Emoji / sticker slots per boost tier (Discord guarantees).
_EMOJI_SLOTS = {0: 50, 1: 100, 2: 150, 3: 250}
_STICKER_SLOTS = {0: 5, 1: 15, 2: 30, 3: 60}


class NoParams(BaseModel):
    """Marker model for read-only tools that take no parameters."""

    model_config = ConfigDict(extra="forbid")


class GetMemberRolesParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: str = Field(description="@mention or numeric user_id")


class _ValidatePlanAction(BaseModel):
    """Inline action shape mirrored from `agent.tools._PlannedAction`.

    Kept identical on purpose: the agent serialises the same structure for
    both `generate_plan` and `validate_plan`, so the JSON shape stays
    interchangeable.
    """

    model_config = ConfigDict(extra="forbid")

    type: str = Field(description="Action type, e.g. 'create_text_channel'")
    params: dict = Field(description="Action parameters")


class ValidatePlanParams(BaseModel):
    """Validate a plan against the current guild state WITHOUT executing.

    Use this before `generate_plan` when you have any doubt about a complex
    plan: it reports conflicts, missing references, and Discord quirks
    (e.g. AutoMod trigger duplicates) so you can adjust before showing the
    plan to the user.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(description="Plan title (for traceability only)")
    actions: list[_ValidatePlanAction] = Field(
        description="Ordered list of actions to validate"
    )


async def list_channels(_: NoParams, guild: discord.Guild) -> str:
    categories = ", ".join(c.name for c in guild.categories)
    text_channels = ", ".join(f"#{c.name}" for c in guild.text_channels)
    voice_channels = ", ".join(c.name for c in guild.voice_channels)
    return (
        f"Categories: {categories}\n"
        f"Text channels: {text_channels}\n"
        f"Voice channels: {voice_channels}"
    )


async def list_roles(_: NoParams, guild: discord.Guild) -> str:
    roles = ", ".join(r.name for r in guild.roles if r.name != "@everyone")
    return f"Roles: {roles}"


async def get_member_roles(params: GetMemberRolesParams, guild: discord.Guild) -> str:
    member = parse_member(guild, params.user)
    if member is None:
        raise ValueError(f"Member not found: {params.user!r}")
    roles = [r.name for r in member.roles if r.name != "@everyone"]
    return f"Roles of {params.user}: {', '.join(roles) or 'none'}"


async def get_server_info(_: NoParams, guild: discord.Guild) -> str:
    return (
        f"Server: {guild.name}\n"
        f"Members: {guild.member_count}\n"
        f"Verification: {guild.verification_level}\n"
        f"Content filter: {guild.explicit_content_filter}\n"
        f"Notifications: {guild.default_notifications}\n"
        f"Boost: tier {guild.premium_tier} ({guild.premium_subscription_count} boosts)\n"
        f"Locale: {guild.preferred_locale}"
    )


async def list_invites(_: NoParams, guild: discord.Guild) -> str:
    invites = await guild.invites()
    if not invites:
        return "No active invites."
    lines = [
        f"- {i.code} → #{i.channel.name if i.channel else '?'} ({i.uses}/{i.max_uses or '∞'} uses)"
        for i in invites
    ]
    return "Invites:\n" + "\n".join(lines)


async def list_webhooks(_: NoParams, guild: discord.Guild) -> str:
    webhooks = await guild.webhooks()
    if not webhooks:
        return "No webhooks."
    lines = [f"- {w.name} → #{w.channel.name if w.channel else '?'}" for w in webhooks]
    return "Webhooks:\n" + "\n".join(lines)


async def list_scheduled_events(_: NoParams, guild: discord.Guild) -> str:
    events = guild.scheduled_events
    if not events:
        return "No scheduled events."
    lines = [f"- {e.name} ({e.entity_type}) — {e.start_time}" for e in events]
    return "Events:\n" + "\n".join(lines)


async def list_automod_rules(_: NoParams, guild: discord.Guild) -> str:
    rules = await guild.fetch_automod_rules()
    if not rules:
        return "No AutoMod rules."
    lines = [f"- {r.name} ({'enabled' if r.enabled else 'disabled'})" for r in rules]
    return "AutoMod rules:\n" + "\n".join(lines)


async def validate_plan_handler(
    params: ValidatePlanParams, guild: discord.Guild
) -> str:
    """Dry-run validator: returns a human-readable report.

    Imports `build_guild_snapshot` lazily to avoid a circular import
    (bot/events.py depends on executor handlers indirectly via the
    registry).
    """
    from architect.bot.events import build_guild_snapshot

    snapshot = build_guild_snapshot(guild)
    actions_raw = [a.model_dump() for a in params.actions]
    issues = validate_plan(actions_raw, snapshot)
    if not issues:
        return f"Plan '{params.title}' validated: no issues found ({len(actions_raw)} actions)."
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    lines = [
        f"Plan '{params.title}': {len(errors)} error(s), {len(warnings)} warning(s)."
    ]
    for issue in errors:
        lines.append(f"❌ action #{issue.action_index + 1}: {issue.message}")
    for issue in warnings:
        lines.append(f"⚠ action #{issue.action_index + 1}: {issue.message}")
    return "\n".join(lines)


class ListThreadsParams(BaseModel):
    """List threads in the guild. If `channel` is given, filter to its parent."""

    model_config = ConfigDict(extra="forbid")

    channel: str | None = Field(
        default=None,
        description="Optional channel name to filter threads by parent",
    )


async def list_threads(params: ListThreadsParams, guild: discord.Guild) -> str:
    threads = list(guild.threads)
    if params.channel:
        name = params.channel.lstrip("#").lower()
        threads = [t for t in threads if t.parent and t.parent.name.lower() == name]
    if not threads:
        return "No active threads." if not params.channel else (
            f"No active threads under #{params.channel}."
        )
    lines: list[str] = []
    for t in threads:
        parent = t.parent.name if t.parent else "?"
        locked = " 🔒locked" if getattr(t, "locked", False) else ""
        archived = " 📦archived" if getattr(t, "archived", False) else ""
        member_count = getattr(t, "member_count", None)
        members = f" ({member_count} members)" if member_count is not None else ""
        lines.append(f"- {t.name} → #{parent}{members}{locked}{archived}")
    return "Active threads:\n" + "\n".join(lines)


async def list_emojis(_: NoParams, guild: discord.Guild) -> str:
    tier = int(getattr(guild, "premium_tier", 0) or 0)
    total = _EMOJI_SLOTS.get(tier, 50)
    emojis = list(guild.emojis)
    if not emojis:
        return f"No custom emojis (0/{total} slots used at boost tier {tier})."
    animated = sum(1 for e in emojis if getattr(e, "animated", False))
    static = len(emojis) - animated
    names = ", ".join(f":{e.name}:" for e in emojis[:50])
    suffix = "" if len(emojis) <= 50 else f" (+{len(emojis) - 50} more)"
    return (
        f"Emojis: {len(emojis)}/{total} slots used at boost tier {tier} "
        f"({static} static, {animated} animated).\n{names}{suffix}"
    )


async def list_stickers(_: NoParams, guild: discord.Guild) -> str:
    tier = int(getattr(guild, "premium_tier", 0) or 0)
    total = _STICKER_SLOTS.get(tier, 5)
    stickers = list(getattr(guild, "stickers", []) or [])
    if not stickers:
        return f"No custom stickers (0/{total} slots used at boost tier {tier})."
    names = ", ".join(s.name for s in stickers)
    return f"Stickers: {len(stickers)}/{total} slots used at boost tier {tier}.\n{names}"


class GetAuditLogParams(BaseModel):
    """Fetch recent audit log entries (who did what when).

    Use this to answer "who deleted #annonces", "who banned Alice", or
    when you suspect a recent change you didn't make.
    """

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Number of entries to return (1-100)",
    )
    action_type: str | None = Field(
        default=None,
        description=(
            "Optional discord.AuditLogAction member name, e.g. "
            "'channel_delete', 'member_kick', 'ban'."
        ),
    )


async def get_audit_log(params: GetAuditLogParams, guild: discord.Guild) -> str:
    # discord.py 2.x's audit_logs accesses `action.value` unconditionally
    # when called with the `action` kwarg, so passing None crashes. Only
    # forward the kwarg when the caller explicitly filtered by action.
    kwargs: dict = {"limit": params.limit}
    if params.action_type:
        action = getattr(discord.AuditLogAction, params.action_type, None)
        if action is None:
            return (
                f"Unknown audit log action {params.action_type!r}. "
                "Use a discord.AuditLogAction member name."
            )
        kwargs["action"] = action
    entries: list[str] = []
    async for entry in guild.audit_logs(**kwargs):
        user = entry.user.name if entry.user else "?"
        target_name = getattr(entry.target, "name", str(entry.target)) if entry.target else "?"
        action_name = entry.action.name if entry.action else "?"
        ts = entry.created_at.isoformat() if entry.created_at else "?"
        reason = f" — {entry.reason}" if entry.reason else ""
        entries.append(f"- `{ts}` **{user}** → `{action_name}` on `{target_name}`{reason}")
    if not entries:
        return "Audit log: no matching entries."
    return "Audit log:\n" + "\n".join(entries)


class GetPermissionChainParams(BaseModel):
    """Explain why a user has (or lacks) permissions in a channel.

    Returns the role chain, the effective base permissions, and any
    channel-level overrides that apply. Use for debugging "why can't
    Alice post in #general".
    """

    model_config = ConfigDict(extra="forbid")

    user: str = Field(description="@mention, name, or numeric user_id")
    channel: str | None = Field(
        default=None,
        description="Optional channel name to compute channel-specific perms",
    )


async def get_permission_chain(
    params: GetPermissionChainParams, guild: discord.Guild
) -> str:
    member = parse_member(guild, params.user)
    if member is None:
        return f"Member not found: {params.user!r}"
    roles = sorted(member.roles, key=lambda r: r.position, reverse=True)
    role_names = [r.name for r in roles if r.name != "@everyone"]
    lines = [
        f"**{member.display_name}** ({member.id})",
        f"Top role: `{member.top_role.name}` (pos {member.top_role.position})",
        f"Roles ({len(role_names)}): {', '.join(role_names) or 'none'}",
    ]
    guild_perms = member.guild_permissions
    granted = sorted(p for p, v in guild_perms if v)
    lines.append(f"Guild-level permissions: {', '.join(granted) or 'none'}")
    if not params.channel:
        return "\n".join(lines)
    name = params.channel.lstrip("#").lower()
    channel = next(
        (c for c in guild.channels if c.name.lower() == name), None
    )
    if channel is None:
        lines.append(f"Channel not found: #{params.channel}")
        return "\n".join(lines)
    lines.append(f"\nChannel `#{channel.name}` overrides:")
    overwrites = getattr(channel, "overwrites", {}) or {}
    everyone_role = guild.default_role
    if everyone_role in overwrites:
        allow, deny = overwrites[everyone_role].pair()
        lines.append(
            f"- @everyone: allow={','.join(sorted(p for p, v in allow if v)) or '∅'} "
            f"deny={','.join(sorted(p for p, v in deny if v)) or '∅'}"
        )
    for role in roles:
        if role in overwrites and role != everyone_role:
            allow, deny = overwrites[role].pair()
            lines.append(
                f"- @{role.name}: allow={','.join(sorted(p for p, v in allow if v)) or '∅'} "
                f"deny={','.join(sorted(p for p, v in deny if v)) or '∅'}"
            )
    if member in overwrites:
        allow, deny = overwrites[member].pair()
        lines.append(
            f"- member-specific: allow={','.join(sorted(p for p, v in allow if v)) or '∅'} "
            f"deny={','.join(sorted(p for p, v in deny if v)) or '∅'}"
        )
    effective = channel.permissions_for(member)
    eff_granted = sorted(p for p, v in effective if v)
    lines.append(f"Effective channel perms: {', '.join(eff_granted) or 'none'}")
    return "\n".join(lines)


class SimulateActionParams(BaseModel):
    """Dry-run a single action against current state.

    Returns the validator issues the action would raise WITHOUT executing
    it. Cheaper than calling `validate_plan` for a single-action probe.
    """

    model_config = ConfigDict(extra="forbid")

    type: str = Field(description="Action type, e.g. 'create_text_channel'")
    params: dict = Field(default_factory=dict, description="Action parameters")


async def simulate_action(
    params: SimulateActionParams, guild: discord.Guild
) -> str:
    from architect.bot.events import build_guild_snapshot

    snapshot = build_guild_snapshot(guild)
    issues = validate_plan(
        [{"type": params.type, "params": params.params}], snapshot
    )
    if not issues:
        return f"Action `{params.type}`: no issues. Would be safe to execute."
    lines = [f"Action `{params.type}` would produce {len(issues)} issue(s):"]
    for issue in issues:
        icon = "❌" if issue.severity == "error" else "⚠"
        lines.append(f"{icon} {issue.message}")
    return "\n".join(lines)


async def check_bot_permissions(_: NoParams, guild: discord.Guild) -> str:
    me = guild.me
    if me is None:
        return "Cannot read bot permissions (membership missing)."
    perms = me.guild_permissions
    required_perms = sorted(set(REQUIRED_PERMISSIONS.values()))
    granted = [p for p in required_perms if getattr(perms, p, False)]
    missing = [p for p in required_perms if not getattr(perms, p, False)]
    lines = [f"Granted permissions: {', '.join(granted) or 'none'}"]
    if missing:
        lines.append(f"Missing permissions: {', '.join(missing)}")
    else:
        lines.append("All required permissions are present.")
    return "\n".join(lines)


__all__ = [
    "GetAuditLogParams",
    "GetMemberRolesParams",
    "GetPermissionChainParams",
    "ListThreadsParams",
    "NoParams",
    "SimulateActionParams",
    "ValidatePlanParams",
    "check_bot_permissions",
    "get_audit_log",
    "get_member_roles",
    "get_permission_chain",
    "get_server_info",
    "list_automod_rules",
    "list_channels",
    "list_emojis",
    "list_invites",
    "list_roles",
    "list_scheduled_events",
    "list_stickers",
    "list_threads",
    "list_webhooks",
    "simulate_action",
    "validate_plan_handler",
]
