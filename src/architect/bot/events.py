from __future__ import annotations

import asyncio
import logging
import re
from time import monotonic
from typing import Any

import discord
from discord.ext import commands

from architect.agent.agent import ArchitectAgent
from architect.agent.events import (
    ClarificationEvent,
    ConfirmationRequiredEvent,
    PlanGeneratedEvent,
    ReadOnlyToolEvent,
    RecordFindingEvent,
    RecordPreferenceEvent,
    ReplyEvent,
)
from architect.bot.history import ConversationHistory
from architect.bot.views import (
    ConfirmResult,
    ConfirmView,
    PlanResult,
    PlanView,
    UndoResult,
    UndoView,
)
from architect.config import settings
from architect.executor.executor import ROLLBACK_ACTIONS, ExecuteError, Executor
from architect.executor.scheduler import build_layers
from architect.executor.validator import validate_plan
from architect.models.snapshot import (
    AutoModRuleInfo,
    ChannelInfo,
    GuildSnapshot,
    RoleInfo,
)
from architect.storage import snapshots as snapshots_store
from architect.storage.guild_context import GuildContext
from architect.storage.guild_context import load as load_guild_context
from architect.storage.guild_context import save as save_guild_context

logger = logging.getLogger(__name__)

MAX_STEPS = 10

_EMBED_LIMIT = 4000  # 96-char margin for Discord markup


def _make_embed(
    description: str,
    title: str | None = None,
    color: discord.Color = discord.Color.blurple(),
) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


_MAX_ERRORS_DISPLAY = 20


def _chunk_text(text: str, limit: int = _EMBED_LIMIT) -> list[str]:
    """Split text into chunks <= limit. Strategy: paragraphs → lines → hard cut.

    Returns [""] for empty input (intentional: lets callers iterate without branching).
    """
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for para in text.split("\n\n"):
        candidate = current + "\n\n" + para if current else para
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(para) <= limit:
                current = para
            else:
                current = ""
                for line in para.split("\n"):
                    candidate = current + "\n" + line if current else line
                    if len(candidate) <= limit:
                        current = candidate
                    else:
                        if current:
                            chunks.append(current)
                        while len(line) > limit:
                            cut = line.rfind(" ", 0, limit)
                            if cut <= 0:
                                cut = limit  # no whitespace → hard cut
                            chunks.append(line[:cut])
                            line = line[cut:]
                        current = line
    if current:
        chunks.append(current)
    return chunks


_TOPIC_MAX = 80
_SERIALIZED_BUDGET = 4000


def _channel_type_label(channel: discord.abc.GuildChannel) -> str:
    if isinstance(channel, discord.TextChannel):
        return "text"
    if isinstance(channel, discord.VoiceChannel):
        return "voice"
    if isinstance(channel, discord.ForumChannel):
        return "forum"
    if isinstance(channel, discord.StageChannel):
        return "stage"
    return type(channel).__name__.removesuffix("Channel").lower() or "channel"


def _channel_line(channel: discord.abc.GuildChannel) -> str:
    """One-line description of a channel: type, name, id, and notable attrs."""
    kind = _channel_type_label(channel)
    prefix = "#" if kind in {"text", "forum"} else ""
    parts = [f"[{kind}] {prefix}{channel.name} (id={channel.id})"]

    topic = getattr(channel, "topic", None) or ""
    if topic:
        topic = topic.strip().replace("\n", " ")
        if len(topic) > _TOPIC_MAX:
            topic = topic[: _TOPIC_MAX - 1] + "…"
        parts.append(f'topic="{topic}"')

    slowmode = getattr(channel, "slowmode_delay", 0)
    if slowmode:
        parts.append(f"slowmode={slowmode}s")
    if getattr(channel, "nsfw", False):
        parts.append("nsfw")

    if isinstance(channel, discord.ForumChannel):
        tags = [t.name for t in getattr(channel, "available_tags", []) or []]
        if tags:
            parts.append(f"tags=[{', '.join(tags)}]")
        flags = getattr(channel, "flags", None)
        if flags is not None and getattr(flags, "require_tag", False):
            parts.append("require_tag")

    return " · ".join(parts)


def _role_line(role: discord.Role) -> str:
    parts = [f"@{role.name} (id={role.id}, pos={role.position})"]
    if role.hoist:
        parts.append("hoist")
    if role.mentionable:
        parts.append("mentionable")
    perms = role.permissions
    if perms.administrator:
        parts.append("perms=administrator")
    else:
        notable = [
            name
            for name in (
                "manage_guild",
                "manage_channels",
                "manage_roles",
                "manage_messages",
                "kick_members",
                "ban_members",
                "moderate_members",
            )
            if getattr(perms, name, False)
        ]
        if notable:
            parts.append(f"perms=[{', '.join(notable)}]")
    return " · ".join(parts)


def _automod_line(rule: object) -> str:
    name = getattr(rule, "name", "?")
    rid = getattr(rule, "id", "?")
    trigger = getattr(rule, "trigger_type", None)
    trigger_name = getattr(trigger, "name", str(trigger)) if trigger is not None else "?"
    enabled = getattr(rule, "enabled", True)
    suffix = "" if enabled else " · disabled"
    return f"{name} (id={rid}, trigger={trigger_name}){suffix}"


_AUTOMOD_TRIGGER_NAME_MAP = {
    1: "keyword",
    3: "spam",
    4: "keyword_preset",
    5: "mention_spam",
}


def _trigger_name(rule: object) -> str:
    trigger = getattr(rule, "trigger_type", None)
    if trigger is None:
        return "?"
    name = getattr(trigger, "name", None)
    if isinstance(name, str):
        return name
    value = getattr(trigger, "value", None)
    if isinstance(value, int):
        return _AUTOMOD_TRIGGER_NAME_MAP.get(value, str(value))
    return str(trigger)


def build_guild_snapshot(
    guild: discord.Guild, automod_rules: list | None = None
) -> GuildSnapshot:
    """Pure-data view of the guild used by the validator and the preview.

    Built once per user turn (cheap — reads from the gateway cache, no HTTP)
    and passed downstream so consumers do not depend on the full
    ``discord.Guild`` object.
    """
    categories: list[ChannelInfo] = []
    channels: list[ChannelInfo] = []
    for ch in guild.channels:
        pos = getattr(ch, "position", 0)
        pos = pos if isinstance(pos, int) else 0
        cid = ch.id if isinstance(ch.id, int) else 0
        if isinstance(ch, discord.CategoryChannel):
            categories.append(
                ChannelInfo(id=cid, name=ch.name, type="category", position=pos)
            )
        else:
            kind = _channel_type_label(ch)
            parent_id = getattr(ch, "category_id", None)
            channels.append(
                ChannelInfo(
                    id=cid,
                    name=ch.name,
                    type=kind,
                    parent_id=parent_id if isinstance(parent_id, int) else None,
                    position=pos,
                )
            )

    roles: list[RoleInfo] = []
    bot_top = 0
    for r in guild.roles:
        if r.name == "@everyone":
            continue
        rid = r.id if isinstance(r.id, int) else 0
        rpos = r.position if isinstance(r.position, int) else 0
        roles.append(RoleInfo(id=rid, name=r.name, position=rpos))
    me = getattr(guild, "me", None)
    if me is not None:
        top = getattr(me, "top_role", None)
        if top is not None:
            pos = getattr(top, "position", 0)
            bot_top = pos if isinstance(pos, int) else 0

    automod_infos: list[AutoModRuleInfo] = []
    for rule in automod_rules or []:
        raw_id = getattr(rule, "id", 0)
        rid = raw_id if isinstance(raw_id, int) else 0
        name = getattr(rule, "name", "?")
        if not isinstance(name, str):
            name = "?"
        automod_infos.append(
            AutoModRuleInfo(id=rid, name=name, trigger_type=_trigger_name(rule))
        )

    return GuildSnapshot(
        categories=categories,
        channels=channels,
        roles=roles,
        automod_rules=automod_infos,
        bot_top_role_position=bot_top,
    )


def _serialize_guild(
    guild: discord.Guild,
    channels=None,
    automod_rules: list | None = None,
) -> str:
    """Render the guild as a structured markdown block for the LLM.

    Channels are grouped under their category (and an "Uncategorized" bucket
    when applicable), each line carries id + type + key attributes so the
    agent can plan edits (not nukes) and reference the right object.

    `automod_rules` are surfaced too so the agent does not blindly try to
    create rules that already exist — Discord enforces a hard cap of 1 rule
    per trigger type and rejects duplicates with HTTP 400.
    """
    all_channels = list(channels) if channels is not None else list(guild.channels)

    def _sort_key(ch: object) -> tuple[int, str]:
        pos = getattr(ch, "position", 0)
        if not isinstance(pos, int):
            pos = 0
        name = getattr(ch, "name", "")
        if not isinstance(name, str):
            name = ""
        return (pos, name)

    all_channels.sort(key=_sort_key)

    categories = [c for c in all_channels if isinstance(c, discord.CategoryChannel)]
    non_cat = [c for c in all_channels if not isinstance(c, discord.CategoryChannel)]
    by_parent: dict[int | None, list] = {}
    for ch in non_cat:
        parent_id = getattr(ch, "category_id", None)
        by_parent.setdefault(parent_id, []).append(ch)

    out: list[str] = ["### Channels"]
    if not categories and not non_cat:
        out.append("(none)")

    for cat in categories:
        out.append(f"- 📁 **{cat.name}** (id={cat.id}, pos={cat.position})")
        children = by_parent.pop(cat.id, [])
        if not children:
            out.append("    (empty)")
        for ch in children:
            out.append(f"    - {_channel_line(ch)}")

    uncategorized = by_parent.pop(None, [])
    if uncategorized:
        out.append("- 📁 **(uncategorized)**")
        for ch in uncategorized:
            out.append(f"    - {_channel_line(ch)}")

    # Orphans (parent_id points at a category not in the list): surface them.
    for parent_id, orphans in by_parent.items():
        out.append(f"- 📁 **(category id={parent_id} not visible)**")
        for ch in orphans:
            out.append(f"    - {_channel_line(ch)}")

    out.append("")
    out.append("### Roles")
    roles = [r for r in guild.roles if r.name != "@everyone"]

    def _role_pos(r: object) -> int:
        pos = getattr(r, "position", 0)
        return -pos if isinstance(pos, int) else 0

    roles.sort(key=_role_pos)  # top of hierarchy first
    if not roles:
        out.append("(none)")
    for r in roles:
        out.append(f"- {_role_line(r)}")

    active_threads = list(getattr(guild, "threads", []) or [])
    if active_threads:
        out.append("")
        out.append("### Active threads")
        for t in active_threads[:20]:
            parent = getattr(t, "parent", None)
            parent_name = getattr(parent, "name", "?")
            out.append(f"- {t.name} (id={t.id}, parent=#{parent_name})")
        if len(active_threads) > 20:
            out.append(f"- … and {len(active_threads) - 20} more")

    if automod_rules:
        out.append("")
        out.append("### AutoMod rules (existing — do not duplicate)")
        for rule in automod_rules:
            out.append(f"- {_automod_line(rule)}")

    text = "\n".join(out)
    if len(text) <= _SERIALIZED_BUDGET:
        return text
    # Overflow: truncate the role list first, then the active threads.
    return text[: _SERIALIZED_BUDGET - 16] + "\n… (truncated)"


_CREATIVE_TURN_PATTERN = re.compile(
    r"\b("
    r"restructur|réorganis|reorganis|refonte|refactor|refacto|"
    r"setup|set\s?up|"
    r"optimi[sz]|simplifi|compact|cozy|netto[iy]|"
    r"redesign|repens|reconcev|"
    r"merge|fusionn|consolid|"
    r"refais|recrée|recree|recommenc"
    r")",
    re.IGNORECASE,
)


def _looks_like_creative_turn(prompt: str) -> bool:
    """Heuristic: does this user prompt ask for a structural change?

    True → route to the (stronger) plan model. False → main model.
    """
    return bool(_CREATIVE_TURN_PATTERN.search(prompt or ""))


def _latest_user_prompt(history: list[dict[str, Any]]) -> str:
    """The most recent user message that's a raw string (not a tool_result)."""
    for msg in reversed(history):
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            return msg["content"]
    return ""


def _should_use_plan_model(history: list[dict[str, Any]]) -> bool:
    """Route to the plan model when the conversation is fresh or the latest
    user turn looks like a structural change request."""
    if len(history) <= 1:
        return True
    last = history[-1]
    if last.get("role") != "user" or not isinstance(last.get("content"), str):
        # Mid-loop, after a tool result — keep the main model.
        return False
    return _looks_like_creative_turn(last["content"])


def _compute_inverse_plan(executed: list[dict]) -> list[dict]:
    """Build an inverse plan from a list of successfully executed actions.

    Walks the list in reverse and uses ``ROLLBACK_ACTIONS`` to invert any
    ``create_*`` action. Non-invertible actions (``edit_*``, ``delete_*``,
    ``create_invite``, ``assign_role``, ``set_channel_permissions``) are
    skipped — v1 of Undo only reverses creations, which is the most common
    case and the only one we can do with full fidelity.
    """
    inverse: list[dict] = []
    for action in reversed(executed):
        atype = action.get("type", "")
        params = action.get("params", {}) or {}
        spec = ROLLBACK_ACTIONS.get(atype)
        if spec is None:
            continue
        inverse_type, param_map = spec
        inverse_params = {
            target: params.get(source) for target, source in param_map.items()
        }
        if any(v is None for v in inverse_params.values()):
            continue
        inverse.append({"type": inverse_type, "params": inverse_params})
    return inverse


def _format_params(params: dict) -> str:
    parts = []
    for key, value in params.items():
        if isinstance(value, list):
            parts.append(f"{key}: [{', '.join(str(v) for v in value)}]")
        else:
            parts.append(f"{key}: {value}")
    return ", ".join(parts)


class BotEvents(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        agent: ArchitectAgent,
        executor: Executor,
        history: ConversationHistory,
    ) -> None:
        from datetime import UTC, datetime

        self.bot = bot
        self._agent = agent
        self._executor = executor
        self._history = history
        self._started_at = datetime.now(UTC)
        # Session stats per guild — bumped from _execute_batch (success /
        # error / rate-limited) so /architect status returns numbers scoped
        # to the guild the command was invoked in.
        self._session_stats: dict[int, dict[str, Any]] = {}
        # Last executed plan per guild — feeds /architect undo.
        self._last_executed: dict[int, list[dict]] = {}
        # asyncio.Lock per channel_id. A user spamming a thread should not
        # cause two agent loops to interleave history writes / tool calls
        # on the same conversation. Cross-guild and cross-channel traffic
        # runs in parallel.
        self._channel_locks: dict[int, asyncio.Lock] = {}

    def _stats_for(self, guild_id: int) -> dict[str, Any]:
        """Return the mutable stats dict for a guild, initializing if needed."""
        stats = self._session_stats.get(guild_id)
        if stats is None:
            stats = {
                "started_at": self._started_at,
                "plans_executed": 0,
                "actions_succeeded": 0,
                "action_errors": 0,
                "rate_limited_actions": 0,
            }
            self._session_stats[guild_id] = stats
        return stats

    def _lock_for(self, channel_id: int) -> asyncio.Lock:
        lock = self._channel_locks.get(channel_id)
        if lock is None:
            lock = asyncio.Lock()
            self._channel_locks[channel_id] = lock
        return lock

    def session_stats(self, guild_id: int) -> dict[str, Any]:
        """Return a shallow copy of the session counters for a guild."""
        return dict(self._stats_for(guild_id))

    def last_executed(self, guild_id: int) -> list[dict]:
        """Return the last successfully executed plan for a guild (or [])."""
        return list(self._last_executed.get(guild_id, []))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if self.bot.user is None:
            return

        in_bot_thread = (
            isinstance(message.channel, discord.Thread)
            and message.channel.owner_id == self.bot.user.id
        )
        is_mention = self.bot.user in message.mentions
        is_reply_to_bot = self._is_reply_to_bot(message)

        if not (is_mention or is_reply_to_bot or in_bot_thread):
            return

        prompt = message.content.replace(f"<@{self.bot.user.id}>", "").strip()

        if not prompt:
            await message.reply("What is your request?")
            return

        guild = message.guild
        if guild is None:
            await message.reply("This bot only works inside a Discord server.")
            return
        if guild.id not in settings.discord_guild_ids:
            await message.reply("This bot is not configured for this server.")
            return

        if isinstance(message.channel, discord.Thread):
            # Already in a thread (bot-owned or otherwise): continue the conversation here.
            thread: discord.abc.Messageable = message.channel
        else:
            thread_name = prompt[:97] + "..." if len(prompt) > 100 else prompt
            try:
                thread = await message.create_thread(
                    name=thread_name, auto_archive_duration=60
                )
            except discord.HTTPException:
                logger.exception(
                    "create_thread failed for channel %s, falling back to channel",
                    message.channel.id,
                )
                thread = message.channel

        # Unified history key: the conversation lives under the thread (or fallback
        # channel) for both the first prompt and every follow-up, including
        # clarifications. Keying off message.channel.id would split the first
        # turn from later turns once the thread is created.
        channel_id = thread.id if hasattr(thread, "id") else message.channel.id

        # Serialize agent turns per channel: two near-simultaneous mentions
        # in the same thread would otherwise interleave history writes and
        # tool calls. Different channels (and different guilds) remain
        # independent — the lock is keyed by channel_id only.
        async with self._lock_for(channel_id):
            self._history.append(channel_id, "user", prompt)

            # Prefer the discord.py gateway cache (`guild.channels`) over a fresh
            # HTTP fetch_channels. The cache is kept up to date by CHANNEL_*
            # events delivered on the gateway, and is already populated by the
            # time we process a user message. fetch_channels was a ~200-400ms
            # round-trip per user message — paid for marginal accuracy.
            # AutoMod rules are not cached by discord.py and matter for plan
            # accuracy (Discord rejects a 2nd rule of the same trigger type), so
            # we fetch them once per turn. Tolerate failures (perms missing).
            automod_rules: list | None = None
            try:
                automod_rules = await guild.fetch_automod_rules()
            except (discord.Forbidden, discord.HTTPException, AttributeError, TypeError):
                logger.debug("fetch_automod_rules unavailable or failed")
            guild_context = _serialize_guild(guild, automod_rules=automod_rules)
            snapshot = build_guild_snapshot(guild, automod_rules=automod_rules)
            server_context = load_guild_context(guild.id)

            status_msg = await thread.send(
                embed=_make_embed("Analyse en cours...", color=discord.Color.orange())
            )

            try:
                await self._run_agent_loop(
                    message,
                    thread,
                    status_msg,
                    guild,
                    channel_id,
                    guild_context,
                    server_context,
                    snapshot,
                )
            except Exception:
                logger.exception("agent loop failed for channel %s", channel_id)
                await self._safe_edit(
                    status_msg,
                    embed=_make_embed("An unexpected error occurred.", color=discord.Color.red()),
                )

    async def _safe_edit(self, msg: discord.Message, **kwargs: Any) -> None:
        """Edit a status message, swallowing HTTPException.

        The plan may delete the channel/thread hosting the bot's status message
        (e.g. a "wipe everything" plan). Subsequent edits then 404 — we log and
        move on instead of bubbling the error up and re-faulting in the outer
        handler.
        """
        try:
            await msg.edit(**kwargs)
        except discord.HTTPException:
            logger.warning("status edit failed (channel/message gone), continuing")

    async def _safe_send(
        self, target: discord.abc.Messageable, **kwargs: Any
    ) -> discord.Message | None:
        try:
            return await target.send(**kwargs)
        except discord.HTTPException:
            logger.warning("status send failed (channel gone), continuing")
            return None

    async def _offer_undo(
        self,
        thread: discord.abc.Messageable,
        guild: discord.Guild,
        inverse_actions: list[dict],
        invoker_id: int,
    ) -> None:
        """Send a one-button view that lets the user undo the last plan.

        The inverse plan is built up-front (cheap, deterministic, no Discord
        I/O), shown as a normal preview if confirmed, then executed via the
        existing batch path. v1 only inverts `create_*` actions — anything
        else from the original plan stays.
        """
        view = UndoView(invoker_id=invoker_id, inverse_actions=inverse_actions)
        n = len(inverse_actions)
        descr = f"{n} action(s) can be reversed (creations only)."
        msg = await self._safe_send(
            thread,
            embed=_make_embed(
                descr, title="Undo available", color=discord.Color.blurple()
            ),
            view=view,
        )
        if msg is None:
            return
        result, _interaction = await view.wait_result()
        if result != UndoResult.CONFIRMED:
            return
        snapshot = build_guild_snapshot(guild)
        confirm_view = PlanView(
            title="Undo last plan",
            actions=inverse_actions,
            invoker_id=invoker_id,
            issues=validate_plan(inverse_actions, snapshot),
            snapshot=snapshot,
        )
        embed, file_content = confirm_view.build_embed()
        if file_content is not None:
            import io

            file = discord.File(io.BytesIO(file_content.encode()), filename="undo.txt")
            await self._safe_send(thread, embed=embed, file=file, view=confirm_view)
        else:
            await self._safe_send(thread, embed=embed, view=confirm_view)
        plan_result = await confirm_view.wait_result()
        if plan_result == PlanResult.CANCELLED:
            await self._safe_send(
                thread,
                embed=_make_embed("Undo cancelled.", color=discord.Color.red()),
            )
            return
        if plan_result == PlanResult.REVIEW:
            # Per-action review on an inverse plan is overkill — treat as
            # confirm-all.
            pass
        progress_msg = await thread.send(
            embed=_make_embed(
                f"Undo in progress... 0/{len(inverse_actions)}",
                color=discord.Color.orange(),
            )
        )
        success, errors, _rolled_back, _executed = await self._execute_batch(
            inverse_actions, guild, progress_msg, atomic=False
        )
        msg_text = f"Undo: {success}/{len(inverse_actions)} reverted."
        if errors:
            msg_text += "\n" + "\n".join(f"• {e}" for e in errors[:_MAX_ERRORS_DISPLAY])
        color = discord.Color.green() if not errors else discord.Color.orange()
        await self._safe_edit(progress_msg, embed=_make_embed(msg_text, color=color))

    def _record_learned_constraint(self, guild: discord.Guild, constraint: str) -> None:
        """Persist a constraint learned from a Discord error to the guild context.

        Best-effort: failures to save are logged but never crash the batch.
        """
        try:
            ctx = load_guild_context(guild.id) or GuildContext(guild_id=guild.id)
            if ctx.record_constraint(constraint):
                save_guild_context(ctx)
        except OSError:
            logger.exception("failed to persist learned constraint for %d", guild.id)

    def _handle_record_finding(
        self,
        event: RecordFindingEvent,
        guild: discord.Guild,
        server_context: GuildContext | None,
    ) -> str:
        """Persist an audit finding emitted by the agent."""
        if server_context is None:
            server_context = GuildContext(guild_id=guild.id)
        category = (
            event.category
            if event.category in ("health", "risk", "opportunity")
            else "risk"
        )
        added = server_context.record_finding(
            category=category, summary=event.summary, severity=event.severity
        )
        try:
            save_guild_context(server_context)
        except OSError:
            logger.exception("failed to persist guild context for %d", guild.id)
            return "finding not saved (storage error)"
        return (
            f"finding recorded: [{category} sev={event.severity}] {event.summary}"
            if added
            else "finding unchanged (duplicate or empty)"
        )

    def _handle_record_preference(
        self,
        event: RecordPreferenceEvent,
        guild: discord.Guild,
        server_context: GuildContext | None,
    ) -> str:
        """Persist a preference/decision to the per-guild JSON store.

        Returns the tool-result string fed back to the model so it can confirm
        the store accepted (or skipped) the entry.
        """
        if server_context is None:
            server_context = GuildContext(guild_id=guild.id)
        kind = event.kind if event.kind in ("preference", "decision") else "preference"
        added = server_context.record(event.text, kind)
        try:
            save_guild_context(server_context)
        except OSError:
            logger.exception("failed to persist guild context for %d", guild.id)
            return "preference not saved (storage error)"
        return (
            f"{kind} recorded: {event.text}"
            if added
            else f"{kind} unchanged (duplicate or empty)"
        )

    def _is_reply_to_bot(self, message: discord.Message) -> bool:
        ref = message.reference
        if ref is None or ref.message_id is None:
            return False
        bot_user = self.bot.user
        if bot_user is None:
            return False
        resolved = ref.resolved
        if isinstance(resolved, discord.Message):
            return resolved.author == bot_user
        cached = ref.cached_message
        if cached is not None:
            return cached.author == bot_user
        return False

    async def _run_agent_loop(
        self,
        message: discord.Message,
        thread: discord.abc.Messageable,
        status_msg: discord.Message,
        guild: discord.Guild,
        channel_id: int,
        guild_context: str,
        server_context: GuildContext | None = None,
        snapshot: GuildSnapshot | None = None,
    ) -> None:
        for _ in range(MAX_STEPS):
            history = self._history.get(channel_id)
            # Route to the plan model when the conversation is fresh OR the
            # latest user prompt looks like a structural change request.
            use_plan_model = _should_use_plan_model(history)
            events = await self._agent.step(
                history, guild_context, server_context=server_context, use_plan_model=use_plan_model
            )

            if not events:
                break

            tool_call_blocks: list[dict] = []
            tool_results: list[tuple[str, str]] = []  # (tool_use_id, result)
            # (tool_use_id, summary) for plan tool calls — collapsed in history
            # after flushing so the rolling window keeps a compact trace instead
            # of carrying the verbose tool_use + tool_result blocks forward.
            plan_compactions: list[tuple[str, str]] = []
            has_tool_calls = False
            stop_loop = False

            # Read-only tool calls are side-effect-free, so we run them all
            # concurrently in one gather() to save N * (HTTP round-trip)
            # latency when the agent emits multiple inspection tools in the
            # same step. Order in tool_results matches the agent's emission
            # order so the conversation stays deterministic.
            readonly_events = [e for e in events if isinstance(e, ReadOnlyToolEvent)]
            if readonly_events:
                if len(readonly_events) == 1:
                    evt = readonly_events[0]
                    await self._safe_edit(
                        status_msg,
                        embed=_make_embed(
                            f"Outil en cours : `{evt.tool_name}`...",
                            color=discord.Color.orange(),
                        ),
                    )
                else:
                    names = ", ".join(f"`{e.tool_name}`" for e in readonly_events)
                    await self._safe_edit(
                        status_msg,
                        embed=_make_embed(
                            f"Outils en parallèle : {names}...",
                            color=discord.Color.orange(),
                        ),
                    )
                results = await asyncio.gather(
                    *(
                        self._executor.execute(e.tool_name, e.params, guild)
                        for e in readonly_events
                    ),
                    return_exceptions=True,
                )
                for evt, result in zip(readonly_events, results, strict=True):
                    if isinstance(result, BaseException):
                        logger.exception(
                            "readonly tool %s failed", evt.tool_name, exc_info=result
                        )
                        result = f"error: {result}"
                    tool_call_blocks.append(
                        {
                            "type": "tool_use",
                            "id": evt.tool_use_id,
                            "name": evt.tool_name,
                            "input": evt.params,
                        }
                    )
                    tool_results.append((evt.tool_use_id, result))
                has_tool_calls = True

            for event in events:
                if isinstance(event, ReadOnlyToolEvent):
                    continue  # already handled above
                if isinstance(event, RecordPreferenceEvent):
                    ack = self._handle_record_preference(event, guild, server_context)
                    if server_context is None:
                        # Stored on first call — reload so subsequent turns see it.
                        server_context = load_guild_context(guild.id)
                    tool_call_blocks.append(
                        {
                            "type": "tool_use",
                            "id": event.tool_use_id,
                            "name": "record_preference",
                            "input": {"text": event.text, "kind": event.kind},
                        }
                    )
                    tool_results.append((event.tool_use_id, ack))
                    has_tool_calls = True
                    continue
                if isinstance(event, RecordFindingEvent):
                    ack = self._handle_record_finding(event, guild, server_context)
                    if server_context is None:
                        server_context = load_guild_context(guild.id)
                    tool_call_blocks.append(
                        {
                            "type": "tool_use",
                            "id": event.tool_use_id,
                            "name": "record_finding",
                            "input": {
                                "category": event.category,
                                "summary": event.summary,
                                "severity": event.severity,
                            },
                        }
                    )
                    tool_results.append((event.tool_use_id, ack))
                    has_tool_calls = True
                    continue
                if isinstance(event, ReplyEvent):
                    chunks = _chunk_text(event.text)
                    await self._safe_edit(status_msg, embed=_make_embed(chunks[0]))
                    for chunk in chunks[1:]:
                        await self._safe_send(thread, embed=_make_embed(chunk))
                    self._history.append(channel_id, "assistant", event.text)
                    stop_loop = True
                    break

                elif isinstance(event, ClarificationEvent):
                    await self._safe_edit(
                        status_msg,
                        embed=_make_embed(
                            event.question,
                            title="Clarification needed",
                            color=discord.Color.yellow(),
                        ),
                    )
                    self._history.append(channel_id, "assistant", event.question)
                    stop_loop = True
                    break

                elif isinstance(event, ConfirmationRequiredEvent):
                    formatted = _format_params(event.params)
                    view = ConfirmView(invoker_id=message.author.id)
                    await thread.send(
                        embed=_make_embed(
                            formatted, title=f"`{event.tool_name}`", color=discord.Color.orange()
                        ),
                        view=view,
                    )
                    confirm_result = await view.wait_result()

                    tool_call_blocks.append(
                        {
                            "type": "tool_use",
                            "id": event.tool_use_id,
                            "name": event.tool_name,
                            "input": event.params,
                        }
                    )
                    has_tool_calls = True

                    if confirm_result == ConfirmResult.CANCELLED_ALL:
                        await thread.send(
                            embed=_make_embed(
                                "All actions were cancelled.", color=discord.Color.red()
                            )
                        )
                        tool_results.append((event.tool_use_id, "cancelled by user"))
                        stop_loop = True
                    elif confirm_result == ConfirmResult.CANCELLED:
                        tool_results.append((event.tool_use_id, "cancelled by user"))
                    else:  # CONFIRMED
                        executed = await self._executor.execute(
                            event.tool_name, event.params, guild
                        )
                        for chunk in _chunk_text(executed):
                            await thread.send(embed=_make_embed(chunk, color=discord.Color.green()))
                        tool_results.append((event.tool_use_id, executed))

                    if stop_loop:
                        break

                elif isinstance(event, PlanGeneratedEvent):
                    logger.info(
                        "plan generated: %s (%d actions)",
                        event.title,
                        len(event.actions),
                        extra={
                            "event": "plan_generated",
                            "guild_id": guild.id,
                            "channel_id": channel_id,
                            "user_id": message.author.id,
                            "action_count": len(event.actions),
                        },
                    )
                    await self._safe_edit(
                        status_msg,
                        embed=_make_embed(
                            "Plan generated, awaiting validation...",
                            color=discord.Color.orange(),
                        ),
                    )
                    issues = (
                        validate_plan(event.actions, snapshot) if snapshot else []
                    )
                    plan_view = PlanView(
                        title=event.title,
                        actions=event.actions,
                        invoker_id=message.author.id,
                        issues=issues,
                        snapshot=snapshot,
                    )
                    embed, file_content = plan_view.build_embed()

                    if file_content is not None:
                        import io

                        file = discord.File(io.BytesIO(file_content.encode()), filename="plan.txt")
                        await thread.send(embed=embed, file=file, view=plan_view)
                    else:
                        await thread.send(embed=embed, view=plan_view)

                    plan_result = await plan_view.wait_result()

                    if plan_result == PlanResult.CANCELLED:
                        result_str = "Plan cancelled by user."
                        await self._safe_edit(
                            status_msg,
                            embed=_make_embed(result_str, color=discord.Color.red()),
                        )
                    elif plan_result == PlanResult.REVIEW:
                        success, errors = await self._review_batch(
                            event.actions, guild, message.author.id, message, thread
                        )
                        result_str = (
                            f"Review complete: {success}/{len(event.actions)} actions executed."
                        )
                        if errors:
                            displayed_errors = errors[:_MAX_ERRORS_DISPLAY]
                            error_block = "\n".join(f"• {e}" for e in displayed_errors)
                            if len(errors) > _MAX_ERRORS_DISPLAY:
                                error_block += (
                                    f"\n… et {len(errors) - _MAX_ERRORS_DISPLAY} more errors"
                                )
                            result_str += f"\nErreurs :\n{error_block}"
                        color = discord.Color.green() if not errors else discord.Color.orange()
                        await self._safe_edit(
                            status_msg, embed=_make_embed(result_str, color=color)
                        )
                    else:  # CONFIRMED_ALL or CONFIRMED_ATOMIC
                        atomic = plan_result == PlanResult.CONFIRMED_ATOMIC
                        # Forensic snapshot: dump current guild state to disk
                        # so a human can reconstitute manually if the bot
                        # crashes mid-execution. Best-effort — failure here
                        # must not block the user's plan.
                        if snapshot is not None:
                            try:
                                snapshots_store.save_pre_exec_snapshot(
                                    guild.id,
                                    snapshot,
                                    event.title,
                                    list(event.actions),
                                )
                                snapshots_store.prune_old_snapshots(guild.id)
                            except OSError:
                                logger.exception(
                                    "failed to persist pre-exec snapshot for %d",
                                    guild.id,
                                )
                        progress_msg = await thread.send(
                            embed=_make_embed(
                                f"Execution in progress... 0/{len(event.actions)}",
                                color=discord.Color.orange(),
                            )
                        )
                        success, errors, rolled_back, executed = await self._execute_batch(
                            event.actions, guild, progress_msg, atomic=atomic
                        )
                        if executed:
                            # Stash the executed plan so /architect undo can
                            # rebuild the inverse even after the in-thread
                            # UndoView has timed out.
                            self._last_executed[guild.id] = list(executed)
                        logger.info(
                            "plan executed: %d/%d ok, %d rolled back",
                            success,
                            len(event.actions),
                            rolled_back,
                            extra={
                                "event": "plan_executed",
                                "guild_id": guild.id,
                                "channel_id": channel_id,
                                "user_id": message.author.id,
                                "action_count": len(event.actions),
                                "success": success,
                                "rolled_back": rolled_back,
                                "errors": len(errors),
                            },
                        )
                        result_str = f"{success}/{len(event.actions)} actions executed."
                        if rolled_back:
                            result_str += f"\n{rolled_back} action(s) reverted by atomic rollback."
                        if errors:
                            displayed_errors = errors[:_MAX_ERRORS_DISPLAY]
                            error_block = "\n".join(f"• {e}" for e in displayed_errors)
                            if len(errors) > _MAX_ERRORS_DISPLAY:
                                error_block += (
                                    f"\n… et {len(errors) - _MAX_ERRORS_DISPLAY} more errors"
                                )
                            result_str += f"\nErreurs :\n{error_block}"
                        color = discord.Color.green() if not errors else discord.Color.orange()
                        await self._safe_edit(
                            status_msg, embed=_make_embed(result_str, color=color)
                        )
                        if success > 0 and executed:
                            inverse_actions = _compute_inverse_plan(executed)
                            if inverse_actions:
                                await self._offer_undo(
                                    thread,
                                    guild,
                                    inverse_actions,
                                    invoker_id=message.author.id,
                                )

                    # Add to history as tool_call + result
                    tool_call_blocks.append(
                        {
                            "type": "tool_use",
                            "id": event.tool_use_id,
                            "name": "generate_plan",
                            "input": {"title": event.title, "actions": event.actions},
                        }
                    )
                    tool_results.append((event.tool_use_id, result_str))
                    plan_compactions.append(
                        (
                            event.tool_use_id,
                            f"Plan « {event.title} » exécuté — {result_str}".replace("\n", " "),
                        )
                    )
                    has_tool_calls = True
                    stop_loop = True
                    break

            # Flush tool calls + results to history in the correct Anthropic order
            if has_tool_calls:
                self._history.append_assistant_tool_calls(channel_id, tool_call_blocks)
                for tool_use_id, result in tool_results:
                    self._history.append_tool_result(channel_id, tool_use_id, result)
                # Collapse plan tool_use + tool_result pairs into a single short
                # assistant message: keeps the conversation coherent, prevents
                # 1-2KB tool blocks from saturating the rolling window.
                for tool_use_id, summary in plan_compactions:
                    self._history.compact_tool_pair(channel_id, tool_use_id, summary)

            if stop_loop or not has_tool_calls:
                break

    async def _run_action_with_rate_limit_signal(
        self,
        action_type: str,
        params: dict,
        guild: discord.Guild,
        state: dict,
    ) -> None:
        """Run one action; if it takes > 3 s (typical 429 backoff), set the
        ``rate_limited`` flag on the shared state so the progress ticker can
        surface a notice. The ticker — not this function — owns the message.
        """
        task = asyncio.create_task(
            self._executor.execute(action_type, params, guild, strict=True)
        )
        t0 = monotonic()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=3.0)
        except TimeoutError:
            state["rate_limited"] = state.get("rate_limited", 0) + 1
            state["rate_limited_total"] = state.get("rate_limited_total", 0) + 1
            try:
                await task
            finally:
                elapsed = monotonic() - t0
                state["rate_limited"] = max(state.get("rate_limited", 1) - 1, 0)
                if elapsed > 5.0:
                    logger.info(
                        "rate-limited action took %.1fs",
                        elapsed,
                        extra={"event": "rate_limited_action", "tool_name": action_type},
                    )

    async def _progress_ticker(
        self, progress_msg: discord.Message, state: dict, interval: float = 1.0
    ) -> None:
        """Refresh progress_msg every `interval` seconds while the batch runs.

        Reads from a dict shared with the batch loop. Cancellation is the
        intended termination path — `finally` in the batch ensures one last
        edit reflects the terminal state.
        """
        try:
            while not state.get("done"):
                completed = state.get("completed", 0)
                total = state.get("total", 0)
                rate_limited = state.get("rate_limited", 0)
                errors = state.get("errors", 0)
                status = f"Execution in progress... {completed}/{total}"
                if rate_limited:
                    status += " — ⏳ rate-limited by Discord, waiting..."
                if errors:
                    status += f"\n{errors} erreur(s)"
                embed = discord.Embed(description=status, color=discord.Color.orange())
                try:
                    await progress_msg.edit(embed=embed)
                except discord.HTTPException:
                    logger.warning("progress_msg edit failed in ticker, continuing")
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            return

    async def _execute_batch(
        self,
        actions: list[dict],
        guild: discord.Guild,
        progress_msg: discord.Message,
        atomic: bool = False,
    ) -> tuple[int, list[str], int, list[dict]]:
        """Execute actions in topological layers — parallel within each layer.

        Layering comes from ``executor.scheduler.build_layers``: actions in
        the same layer have no producer/consumer relationship by name and
        run concurrently. Layers run sequentially.

        Atomic mode: if any action in a layer fails, we wait for the rest of
        the layer to finish (so partial state is consistent) then roll back
        the successful creations in reverse order before returning.

        A 1-Hz ticker task refreshes the progress message in parallel — the
        action runners only mutate shared state, never the message directly.

        Returns ``(success - rollback, errors, rollback_count, executed)``
        where ``executed`` is the in-order list of successful actions that
        were NOT rolled back, used by the post-exec Undo flow.
        """
        total = len(actions)
        state: dict = {
            "completed": 0,
            "total": total,
            "rate_limited": 0,
            "errors": 0,
            "done": False,
        }
        completed: list[dict] = []
        completed_indices: set[int] = set()
        errors: list[str] = []
        layers = build_layers(actions)
        stopped_early = False

        ticker = asyncio.create_task(self._progress_ticker(progress_msg, state))

        async def run_one(idx: int) -> tuple[int, BaseException | None]:
            action = actions[idx]
            atype = action.get("type", "")
            params = action.get("params", {}) or {}
            try:
                await self._run_action_with_rate_limit_signal(atype, params, guild, state)
                return idx, None
            except (ExecuteError, ValueError, NotImplementedError) as exc:
                logger.exception(
                    "action %s failed in batch",
                    atype,
                    extra={"event": "action_failed", "tool_name": atype},
                )
                return idx, exc
            except Exception as exc:
                logger.exception("unexpected error on %s in batch", atype)
                return idx, exc

        try:
            for layer in layers:
                results = await asyncio.gather(
                    *(run_one(idx) for idx in layer), return_exceptions=False
                )
                for idx, exc in results:
                    action = actions[idx]
                    atype = action.get("type", "")
                    params = action.get("params", {}) or {}
                    if exc is None:
                        state["completed"] += 1
                        self._stats_for(guild.id)["actions_succeeded"] += 1
                        completed.append(action)
                        completed_indices.add(idx)
                    else:
                        state["errors"] += 1
                        self._stats_for(guild.id)["action_errors"] += 1
                        errors.append(f"{atype}({params.get('name', '?')}): {exc}")
                        if isinstance(exc, ExecuteError) and exc.learned_constraint:
                            self._record_learned_constraint(
                                guild, exc.learned_constraint
                            )
                if errors and atomic:
                    stopped_early = True
                    break
        finally:
            state["done"] = True
            self._stats_for(guild.id)["rate_limited_actions"] += int(
                state.get("rate_limited_total", 0)
            )
            ticker.cancel()
            try:
                await ticker
            except asyncio.CancelledError:
                pass

        # Re-sort `completed` by the original plan order so the undo flow
        # produces a deterministic inverse regardless of intra-layer
        # gather ordering.
        completed = [actions[i] for i in sorted(completed_indices)]

        rollback_count = 0
        executed = list(completed)
        if stopped_early and atomic and completed:
            try:
                await progress_msg.edit(
                    embed=discord.Embed(
                        description=f"Erreur — rollback en cours de {len(completed)} actions...",
                        color=discord.Color.red(),
                    )
                )
            except discord.HTTPException:
                pass
            rollback_count = await self._rollback(completed, guild)
            if rollback_count:
                executed = executed[: max(len(executed) - rollback_count, 0)]

        success_count = state["completed"]
        self._stats_for(guild.id)["plans_executed"] += 1
        return success_count - rollback_count, errors, rollback_count, executed

    async def _rollback(self, completed: list[dict], guild: discord.Guild) -> int:
        """Revert creations in reverse order. Return the count of reverted actions."""
        count = 0
        for action in reversed(completed):
            action_type = action.get("type", "")
            params = action.get("params", {})
            inverse = ROLLBACK_ACTIONS.get(action_type)
            if inverse is None:
                continue
            inverse_type, param_map = inverse
            inverse_params = {target: params.get(source) for target, source in param_map.items()}
            if any(v is None for v in inverse_params.values()):
                continue
            try:
                await self._executor.execute(inverse_type, inverse_params, guild, strict=True)
                count += 1
            except Exception:
                logger.exception("rollback failed for %s → %s", action_type, inverse_type)
        return count

    async def _review_batch(
        self,
        actions: list[dict],
        guild: discord.Guild,
        invoker_id: int,
        message: discord.Message,
        thread: discord.abc.Messageable | None = None,
    ) -> tuple[int, list[str]]:
        """
        Review each action one by one using PlanReviewView.
        If AUTO_REST is clicked, switches to _execute_batch for remaining actions.
        Returns (success_count, errors).
        """
        from .views import PlanReviewResult, PlanReviewView

        dest = thread if thread is not None else message.channel
        success_count = 0
        errors: list[str] = []

        for i, action in enumerate(actions):
            action_type = action.get("type", "")
            params = action.get("params", {})
            formatted = _format_params(params)

            view = PlanReviewView(invoker_id=invoker_id)
            await dest.send(
                embed=_make_embed(
                    f"[{i + 1}/{len(actions)}] {formatted}",
                    title=f"`{action_type}`",
                    color=discord.Color.orange(),
                ),
                view=view,
            )
            result = await view.wait_result()

            if result == PlanReviewResult.CANCELLED_ALL:
                await dest.send(embed=_make_embed("Review cancelled.", color=discord.Color.red()))
                break
            elif result == PlanReviewResult.SKIPPED:
                continue
            elif result == PlanReviewResult.AUTO_REST:
                # Execute remaining actions (including current one) in batch
                remaining = actions[i:]
                progress_msg = await dest.send(
                    embed=_make_embed(
                        f"Execution in progress... 0/{len(remaining)}", color=discord.Color.orange()
                    )
                )
                batch_success, batch_errors, _, _ = await self._execute_batch(
                    remaining, guild, progress_msg
                )
                success_count += batch_success
                errors.extend(batch_errors)
                break
            else:  # CONFIRMED
                try:
                    await self._executor.execute(action_type, params, guild)
                    success_count += 1
                    await dest.send(
                        embed=_make_embed(
                            f"`{action_type}`: {params.get('name', '?')}",
                            color=discord.Color.green(),
                        )
                    )
                except Exception as e:
                    logger.exception("action %s failed during review", action_type)
                    error_msg = f"{action_type}: {e}"
                    errors.append(error_msg)
                    await dest.send(
                        embed=_make_embed(error_msg, title="Erreur", color=discord.Color.red())
                    )

        return success_count, errors
