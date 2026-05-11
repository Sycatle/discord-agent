"""`/architect` slash command group — status, prefs, snapshots, undo.

Read-only inspection surface for the bot's session and per-guild state.
Built on top of the existing storage modules; the cog holds no state of
its own beyond a reference to the BotEvents cog (for session stats and
the last-executed plan per guild).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import discord
from discord import app_commands
from discord.ext import commands

from architect.bot.events import BotEvents, _compute_inverse_plan, build_guild_snapshot
from architect.bot.views import ConfirmResult, ConfirmView, PlanResult, PlanView
from architect.executor.validator import validate_plan
from architect.storage import snapshots as snapshots_store
from architect.storage.guild_context import GuildContext
from architect.storage.guild_context import load as load_guild_context
from architect.storage.guild_context import save as save_guild_context

_SNAPSHOTS_DISPLAYED = 10
_INVERSE_MAX_ACTIONS = 25


def _format_duration(seconds: float) -> str:
    seconds = int(max(seconds, 0))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


class ArchitectCommand(commands.Cog):
    """Slash command surface for inspecting and operating the architect bot."""

    def __init__(self, bot: commands.Bot, events: BotEvents) -> None:
        self.bot = bot
        self._events = events

    architect_group = app_commands.Group(
        name="architect",
        description="Inspect the architect bot session, preferences, and snapshots",
    )

    # ── status ──────────────────────────────────────────────────────────────

    @architect_group.command(name="status", description="Session uptime and counters")
    async def status(self, interaction: discord.Interaction) -> None:
        stats = self._events.session_stats()
        started_at = stats.get("started_at")
        uptime = (
            _format_duration(
                (datetime.now(UTC) - started_at).total_seconds()
            )
            if isinstance(started_at, datetime)
            else "?"
        )
        embed = discord.Embed(
            title="Architect — status",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Uptime", value=uptime, inline=True)
        embed.add_field(
            name="Plans exec", value=str(stats.get("plans_executed", 0)), inline=True
        )
        embed.add_field(
            name="Actions OK", value=str(stats.get("actions_succeeded", 0)), inline=True
        )
        embed.add_field(
            name="Errors", value=str(stats.get("action_errors", 0)), inline=True
        )
        embed.add_field(
            name="Rate-limited",
            value=str(stats.get("rate_limited_actions", 0)),
            inline=True,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── prefs ───────────────────────────────────────────────────────────────

    @architect_group.command(name="prefs", description="List persisted preferences")
    async def prefs(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command must be used inside a server.", ephemeral=True
            )
            return
        ctx = load_guild_context(interaction.guild_id) or GuildContext(
            guild_id=interaction.guild_id
        )
        prefs_text = "\n".join(f"- {p}" for p in ctx.preferences) or "*none*"
        decisions_text = (
            "\n".join(f"- {d}" for d in ctx.recent_decisions) or "*none*"
        )
        embed = discord.Embed(
            title="Architect — preferences", color=discord.Color.blurple()
        )
        embed.add_field(name="Preferences", value=prefs_text, inline=False)
        embed.add_field(name="Recent decisions", value=decisions_text, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @architect_group.command(
        name="prefs-clear", description="Clear all preferences and decisions"
    )
    async def prefs_clear(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command must be used inside a server.", ephemeral=True
            )
            return
        ctx = load_guild_context(interaction.guild_id)
        if ctx is None or (not ctx.preferences and not ctx.recent_decisions):
            await interaction.response.send_message(
                "Nothing to clear.", ephemeral=True
            )
            return
        ctx.preferences = []
        ctx.recent_decisions = []
        save_guild_context(ctx)
        await interaction.response.send_message(
            "✓ Preferences and decisions cleared.", ephemeral=True
        )

    # ── snapshots ───────────────────────────────────────────────────────────

    @architect_group.command(
        name="snapshots", description="List the most recent pre-exec snapshots"
    )
    async def snapshots(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command must be used inside a server.", ephemeral=True
            )
            return
        paths = snapshots_store.list_snapshots(interaction.guild_id)
        if not paths:
            await interaction.response.send_message(
                "No snapshot recorded yet.", ephemeral=True
            )
            return
        lines: list[str] = []
        for path in paths[:_SNAPSHOTS_DISPLAYED]:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            ts = payload.get("timestamp", "?")
            title = payload.get("plan_title", "?")
            action_count = len(payload.get("plan_actions", []))
            lines.append(f"- `{ts}` — **{title}** ({action_count} actions)")
        embed = discord.Embed(
            title="Architect — recent snapshots",
            description="\n".join(lines) or "*nothing readable*",
            color=discord.Color.blurple(),
        )
        if len(paths) > _SNAPSHOTS_DISPLAYED:
            embed.set_footer(
                text=f"+ {len(paths) - _SNAPSHOTS_DISPLAYED} older not shown"
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── audit ───────────────────────────────────────────────────────────────

    @architect_group.command(
        name="audit",
        description="Ask the agent to audit this server (read-only deep dive)",
    )
    async def audit(self, interaction: discord.Interaction) -> None:
        """Post an audit kickoff message in the current channel.

        The agent picks it up via the normal on_message flow and chains
        as many read-only tools as needed (system prompt encourages this).
        Findings get persisted via `record_finding`.
        """
        if interaction.channel is None:
            await interaction.response.send_message(
                "Audit must be triggered inside a channel.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            "Audit lancé — l'agent va analyser le serveur en read-only.",
            ephemeral=True,
        )
        bot_user = self.bot.user
        mention = bot_user.mention if bot_user else "@bot"
        await interaction.channel.send(
            f"{mention} audit complet du serveur : "
            "santé, risques, opportunités. "
            "Enchaîne les outils read-only nécessaires, puis utilise "
            "`record_finding` pour chaque observation importante. "
            "Termine par une synthèse structurée."
        )

    # ── undo ────────────────────────────────────────────────────────────────

    @architect_group.command(
        name="undo", description="Undo the last executed plan for this server"
    )
    async def undo(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None or interaction.guild is None:
            await interaction.response.send_message(
                "This command must be used inside a server.", ephemeral=True
            )
            return
        last_executed = self._events.last_executed(interaction.guild_id)
        if not last_executed:
            await interaction.response.send_message(
                "Nothing to undo (no plan executed in this session).",
                ephemeral=True,
            )
            return
        inverse = _compute_inverse_plan(last_executed)
        if not inverse:
            await interaction.response.send_message(
                "Nothing to undo — the last plan only contained edits/deletes "
                "(not yet reversible).",
                ephemeral=True,
            )
            return
        if len(inverse) > _INVERSE_MAX_ACTIONS:
            inverse = inverse[:_INVERSE_MAX_ACTIONS]
        snapshot = build_guild_snapshot(interaction.guild)
        view = PlanView(
            title="Undo last plan",
            actions=inverse,
            invoker_id=interaction.user.id,
            issues=validate_plan(inverse, snapshot),
            snapshot=snapshot,
        )
        embed, _ = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

        plan_result = await view.wait_result()
        if plan_result == PlanResult.CANCELLED:
            return
        confirm = ConfirmView(invoker_id=interaction.user.id)
        msg = await interaction.followup.send(
            embed=discord.Embed(
                title="Confirm undo",
                description=f"Run {len(inverse)} reverse action(s) now?",
                color=discord.Color.orange(),
            ),
            view=confirm,
        )
        result = await confirm.wait_result()
        if result != ConfirmResult.CONFIRMED:
            return
        progress = await msg.edit(
            embed=discord.Embed(
                description=f"Undo in progress... 0/{len(inverse)}",
                color=discord.Color.orange(),
            ),
            view=None,
        )
        success, errors, _rolled, _executed = await self._events._execute_batch(
            inverse, interaction.guild, progress, atomic=False
        )
        text = f"Undo: {success}/{len(inverse)} reverted."
        if errors:
            text += "\n" + "\n".join(f"- {e}" for e in errors[:5])
        await progress.edit(
            embed=discord.Embed(
                description=text,
                color=discord.Color.green() if not errors else discord.Color.orange(),
            )
        )
