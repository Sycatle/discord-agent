from __future__ import annotations

import asyncio
import enum
from typing import Any

import discord

from architect.executor.validator import PlanIssue, validate_plan
from architect.models.snapshot import GuildSnapshot

_SELECT_MAX_OPTIONS = 25


class ConfirmResult(enum.Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    CANCELLED_ALL = "cancelled_all"


class ConfirmView(discord.ui.View):
    def __init__(self, invoker_id: int) -> None:
        super().__init__(timeout=120)
        self.invoker_id = invoker_id
        self._future: asyncio.Future[ConfirmResult] | None = None

    def _is_invoker(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.invoker_id

    def _get_future(self) -> asyncio.Future[ConfirmResult]:
        if self._future is None:
            self._future = asyncio.get_running_loop().create_future()
        return self._future

    async def wait_result(self) -> ConfirmResult:
        """Await until user clicks a button or timeout."""
        fut = self._get_future()
        await self.wait()
        if fut.done():
            return fut.result()
        return ConfirmResult.CANCELLED

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message(
                "Only the message author can use this button.", ephemeral=True
            )
            return
        await interaction.response.defer()
        self._get_future().set_result(ConfirmResult.CONFIRMED)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message(
                "Only the message author can use this button.", ephemeral=True
            )
            return
        await interaction.response.defer()
        self._get_future().set_result(ConfirmResult.CANCELLED)
        self.stop()

    @discord.ui.button(label="Cancel all", style=discord.ButtonStyle.danger, emoji="🛑")
    async def cancel_all(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message(
                "Only the message author can use this button.", ephemeral=True
            )
            return
        await interaction.response.defer()
        self._get_future().set_result(ConfirmResult.CANCELLED_ALL)
        self.stop()


class PlanResult(enum.Enum):
    CONFIRMED_ALL = "confirmed_all"
    CONFIRMED_ATOMIC = "confirmed_atomic"
    REVIEW = "review"
    CANCELLED = "cancelled"


_EMBED_DIFF_LIMIT = 3500


def _diff_lines(
    actions: list[dict[str, Any]], snapshot: GuildSnapshot | None
) -> list[str]:
    """Render the plan as a diff grouped by target category.

    Channels appear under their target category with +/~/-/. roles, automod,
    server-level changes get their own sections. The snapshot is optional —
    without it we still produce sensible output, just without the existing
    category resolution.
    """
    # Group channel changes by their target category name.
    by_cat: dict[str, list[str]] = {}
    cat_lines: list[str] = []
    role_lines: list[str] = []
    automod_lines: list[str] = []
    other_lines: list[str] = []

    def emoji_for(kind: str) -> str:
        return {"text": "#", "voice": "voice:", "forum": "#", "stage": "stage:"}.get(
            kind, "#"
        )

    for a in actions:
        atype = a.get("type", "")
        params = a.get("params", {}) or {}
        name = params.get("name") or params.get("channel") or params.get("role") or "?"

        if atype == "create_category":
            cat_lines.append(f"+ 📁 **{name}**")
        elif atype == "delete_channel":
            # Could be a channel or a category — best-effort lookup via snapshot.
            is_cat = (
                snapshot is not None and snapshot.category_by_name(name) is not None
            )
            if is_cat:
                cat_lines.append(f"- 📁 **{name}**")
            else:
                parent = "(uncategorized)"
                if snapshot is not None:
                    info = snapshot.channel_by_name(name)
                    if info is not None and info.parent_id is not None:
                        parent_info = next(
                            (c for c in snapshot.categories if c.id == info.parent_id),
                            None,
                        )
                        if parent_info is not None:
                            parent = parent_info.name
                by_cat.setdefault(parent, []).append(f"- `#{name}`")
        elif atype in (
            "create_text_channel",
            "create_voice_channel",
            "create_forum_channel",
            "create_stage_channel",
        ):
            kind = atype.removeprefix("create_").removesuffix("_channel")
            cat = params.get("category") or "(uncategorized)"
            prefix = emoji_for(kind)
            by_cat.setdefault(cat, []).append(f"+ `{prefix}{name}` ({kind})")
        elif atype == "edit_channel":
            target = params.get("channel", "?")
            new_name = params.get("name")
            new_parent = params.get("parent_id")
            label = f"~ `#{target}`"
            edits: list[str] = []
            if new_name and new_name != target:
                edits.append(f"→ `{new_name}`")
            if new_parent:
                edits.append(f"→ 📁 {new_parent}")
            if params.get("topic") is not None:
                edits.append("topic")
            if params.get("slowmode") is not None:
                edits.append("slowmode")
            if params.get("nsfw") is not None:
                edits.append("nsfw")
            if params.get("position") is not None:
                edits.append(f"pos={params['position']}")
            if edits:
                label += " " + " ".join(edits)
            # Anchor under the original parent if known.
            parent = "(uncategorized)"
            if snapshot is not None:
                info = snapshot.channel_by_name(target)
                if info is not None and info.parent_id is not None:
                    parent_info = next(
                        (c for c in snapshot.categories if c.id == info.parent_id),
                        None,
                    )
                    if parent_info is not None:
                        parent = parent_info.name
            by_cat.setdefault(parent, []).append(label)
        elif atype == "set_channel_permissions":
            target = params.get("channel", "?")
            role = params.get("role", "?")
            parent = "(uncategorized)"
            if snapshot is not None:
                info = snapshot.channel_by_name(target)
                if info is not None and info.parent_id is not None:
                    parent_info = next(
                        (c for c in snapshot.categories if c.id == info.parent_id),
                        None,
                    )
                    if parent_info is not None:
                        parent = parent_info.name
            by_cat.setdefault(parent, []).append(f"~ `#{target}` perms({role})")
        elif atype == "create_role":
            role_lines.append(f"+ @{name}")
        elif atype == "edit_role":
            target = params.get("role", "?")
            new_name = params.get("name")
            label = f"~ @{target}"
            if new_name and new_name != target:
                label += f" → @{new_name}"
            role_lines.append(label)
        elif atype == "delete_role":
            role_lines.append(f"- @{params.get('role', '?')}")
        elif atype in ("assign_role", "remove_role"):
            user = params.get("user", "?")
            role = params.get("role", "?")
            sign = "+" if atype == "assign_role" else "-"
            role_lines.append(f"{sign} @{role} {user}")
        elif atype.startswith("create_automod"):
            automod_lines.append(f"+ AutoMod `{name}` ({params.get('trigger_type', '?')})")
        elif atype.startswith("edit_automod"):
            automod_lines.append(f"~ AutoMod `{params.get('rule', '?')}`")
        elif atype.startswith("delete_automod"):
            automod_lines.append(f"- AutoMod `{params.get('rule', '?')}`")
        else:
            other_lines.append(f"• `{atype}`: {name}")

    out: list[str] = []
    if cat_lines:
        out.extend(cat_lines)
        out.append("")
    for cat_name in sorted(by_cat.keys()):
        out.append(f"📁 **{cat_name}**")
        out.extend(by_cat[cat_name])
        out.append("")
    if role_lines:
        out.append("**Roles**")
        out.extend(role_lines)
        out.append("")
    if automod_lines:
        out.append("**AutoMod**")
        out.extend(automod_lines)
        out.append("")
    if other_lines:
        out.append("**Other**")
        out.extend(other_lines)
        out.append("")
    while out and out[-1] == "":
        out.pop()
    return out


class _PlanActionSelect(discord.ui.Select["PlanView"]):
    """Select menu that lets the invoker remove an action from the plan.

    Lives on the PlanView. On selection: pops the chosen index, recomputes
    validator issues, rebuilds the embed, and rewires the select with the
    new (shorter) action list. Bounded by Discord's 25-option Select cap.
    """

    def __init__(self, plan_view: PlanView) -> None:
        options = self._build_options(plan_view.actions)
        super().__init__(
            placeholder=(
                "Retirer une action…"
                if options
                else "Plan vide — Cancel pour fermer"
            ),
            options=options or [discord.SelectOption(label="(none)", value="-1")],
            min_values=1,
            max_values=1,
            disabled=not options,
        )

    @staticmethod
    def _build_options(actions: list[dict[str, Any]]) -> list[discord.SelectOption]:
        opts: list[discord.SelectOption] = []
        for i, action in enumerate(actions[:_SELECT_MAX_OPTIONS]):
            atype = action.get("type", "?")
            params = action.get("params", {}) or {}
            name = (
                params.get("name")
                or params.get("channel")
                or params.get("role")
                or "?"
            )
            label = f"#{i + 1} {atype}: {name}"
            # SelectOption labels are capped at 100 chars by Discord.
            opts.append(discord.SelectOption(label=label[:100], value=str(i)))
        return opts

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if view is None or not view._is_invoker(interaction):
            await interaction.response.send_message(
                "Only the message author can edit this plan.", ephemeral=True
            )
            return
        try:
            idx = int(self.values[0])
        except (TypeError, ValueError):
            await interaction.response.defer()
            return
        if idx < 0 or idx >= len(view.actions):
            await interaction.response.defer()
            return
        del view.actions[idx]
        view.issues = (
            validate_plan(view.actions, view.snapshot) if view.snapshot else []
        )
        view._rewire_select()
        view._sync_confirm_buttons()
        embed, _ = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class PlanView(discord.ui.View):
    def __init__(
        self,
        title: str,
        actions: list[dict[str, Any]],
        invoker_id: int,
        *,
        issues: list[PlanIssue] | None = None,
        snapshot: GuildSnapshot | None = None,
    ) -> None:
        super().__init__(timeout=300)
        self.title = title
        self.actions = actions
        self.invoker_id = invoker_id
        self.issues = issues or []
        self.snapshot = snapshot
        self._future: asyncio.Future[PlanResult] | None = None
        # Add the action-removal Select. Buttons are auto-added by
        # discord.ui via the @discord.ui.button decorators below.
        self._select = _PlanActionSelect(self)
        self.add_item(self._select)
        self._sync_confirm_buttons()

    def _rewire_select(self) -> None:
        """Rebuild the Select to reflect the current action list.

        Called after the user removes an action via the menu — indices must
        renumber and the placeholder updates when the plan becomes empty.
        """
        self.remove_item(self._select)
        self._select = _PlanActionSelect(self)
        self.add_item(self._select)

    def _sync_confirm_buttons(self) -> None:
        """Disable confirm buttons when the plan is empty.

        Cancel stays enabled so the user can always close the prompt.
        """
        is_empty = not self.actions
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                label = (child.label or "").lower()
                if label.startswith("cancel"):
                    continue
                child.disabled = is_empty

    def _is_invoker(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.invoker_id

    def _get_future(self) -> asyncio.Future[PlanResult]:
        if self._future is None:
            self._future = asyncio.get_running_loop().create_future()
        return self._future

    async def wait_result(self) -> PlanResult:
        fut = self._get_future()
        await self.wait()
        if fut.done():
            return fut.result()
        return PlanResult.CANCELLED

    def build_embed(self) -> tuple[discord.Embed, str | None]:
        """Return (embed, file_content_or_none) for the plan.

        Layout:
          - Description line: action counts grouped by intent (creations/
            modifications/deletions).
          - "Warnings" field with any validator issues (errors first).
          - "Diff" field with actions grouped by target category, +/~/-.

        Falls back to a .txt attachment when the rendered diff exceeds the
        embed budget — long plans never silently drop content.
        """
        from collections import Counter

        type_counts = Counter(a.get("type", "unknown") for a in self.actions)

        domain_buckets = {
            "creations": (
                "create_category",
                "create_text_channel",
                "create_voice_channel",
                "create_forum_channel",
                "create_stage_channel",
                "create_role",
                "create_invite",
                "create_webhook",
                "create_scheduled_event",
                "create_automod_rule",
            ),
            "modifications": (
                "edit_channel",
                "edit_role",
                "edit_member",
                "edit_webhook",
                "edit_scheduled_event",
                "edit_automod_rule",
                "edit_server",
                "edit_welcome_screen",
                "set_channel_permissions",
                "assign_role",
                "remove_role",
            ),
            "deletions": (
                "delete_channel",
                "delete_invite",
                "delete_webhook",
                "delete_role",
                "delete_scheduled_event",
                "delete_automod_rule",
            ),
        }
        count_parts = []
        for label, types in domain_buckets.items():
            count = sum(type_counts.get(t, 0) for t in types)
            if count > 0:
                count_parts.append(f"**{count}** {label}")
        unknown = sum(
            c
            for t, c in type_counts.items()
            if not any(t in types for types in domain_buckets.values())
        )
        if unknown:
            count_parts.append(f"**{unknown}** other")
        summary = " · ".join(count_parts) if count_parts else "No actions"

        embed = discord.Embed(
            title=f"📋 Plan — {self.title}",
            description=summary,
            color=discord.Color.blurple(),
        )

        if self.issues:
            errors = [i for i in self.issues if i.severity == "error"]
            warns = [i for i in self.issues if i.severity == "warning"]
            warn_lines: list[str] = []
            for issue in errors[:5]:
                warn_lines.append(f"❌ #{issue.action_index + 1}: {issue.message}")
            for issue in warns[:5]:
                warn_lines.append(f"⚠ #{issue.action_index + 1}: {issue.message}")
            extra = len(self.issues) - len(warn_lines)
            if extra > 0:
                warn_lines.append(f"… and {extra} more")
            if warn_lines:
                embed.add_field(
                    name="Warnings", value="\n".join(warn_lines), inline=False
                )

        diff_lines = _diff_lines(self.actions, self.snapshot)
        diff_text = "\n".join(diff_lines) if diff_lines else "—"
        file_content: str | None = None
        if len(diff_text) > _EMBED_DIFF_LIMIT:
            truncated: list[str] = []
            budget = _EMBED_DIFF_LIMIT
            for line in diff_lines:
                if budget - len(line) - 1 < 0:
                    break
                truncated.append(line)
                budget -= len(line) + 1
            truncated.append("… (truncated, see attached file)")
            diff_text = "\n".join(truncated)
            lines = [f"# Plan: {self.title}", f"Total: {len(self.actions)} actions", ""]
            for i, action in enumerate(self.actions, 1):
                atype = action.get("type", "?")
                params = action.get("params", {})
                lines.append(f"{i}. {atype}: {params}")
            file_content = "\n".join(lines)
        embed.add_field(name="Diff", value=diff_text, inline=False)
        embed.set_footer(text=f"{len(self.actions)} actions total")

        return embed, file_content

    @discord.ui.button(label="Confirm all", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_all(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message(
                "Only the message author can use this button.", ephemeral=True
            )
            return
        await interaction.response.defer()
        self._get_future().set_result(PlanResult.CONFIRMED_ALL)
        self.stop()

    @discord.ui.button(
        label="Atomic (rollback on error)", style=discord.ButtonStyle.primary, emoji="⚛"
    )
    async def confirm_atomic(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message(
                "Only the message author can use this button.", ephemeral=True
            )
            return
        await interaction.response.defer()
        self._get_future().set_result(PlanResult.CONFIRMED_ATOMIC)
        self.stop()

    @discord.ui.button(label="Review", style=discord.ButtonStyle.secondary, emoji="🔍")
    async def review(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message(
                "Only the message author can use this button.", ephemeral=True
            )
            return
        await interaction.response.defer()
        self._get_future().set_result(PlanResult.REVIEW)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message(
                "Only the message author can use this button.", ephemeral=True
            )
            return
        await interaction.response.defer()
        self._get_future().set_result(PlanResult.CANCELLED)
        self.stop()


class UndoResult(enum.Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class UndoView(discord.ui.View):
    """Single-button view shown on the success embed.

    Holds the inverse-actions list so that on click we can pop a ConfirmView
    with the inverse plan and (on confirm) hand it back to the executor.
    Timeout is 10 minutes — long enough for the user to think it over, short
    enough that stale inverses don't sit around forever.
    """

    def __init__(self, invoker_id: int, inverse_actions: list[dict[str, Any]]) -> None:
        super().__init__(timeout=600)
        self.invoker_id = invoker_id
        self.inverse_actions = inverse_actions
        self._future: asyncio.Future[
            tuple[UndoResult, discord.Interaction | None]
        ] | None = None

    def _is_invoker(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.invoker_id

    def _get_future(
        self,
    ) -> asyncio.Future[tuple[UndoResult, discord.Interaction | None]]:
        if self._future is None:
            self._future = asyncio.get_running_loop().create_future()
        return self._future

    async def wait_result(
        self,
    ) -> tuple[UndoResult, discord.Interaction | None]:
        fut = self._get_future()
        await self.wait()
        if fut.done():
            return fut.result()
        return (UndoResult.CANCELLED, None)

    @discord.ui.button(label="Undo last plan", style=discord.ButtonStyle.secondary, emoji="↩")
    async def undo(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message(
                "Only the message author can use this button.", ephemeral=True
            )
            return
        await interaction.response.defer()
        button.disabled = True
        try:
            await interaction.edit_original_response(view=self)
        except discord.HTTPException:
            pass
        self._get_future().set_result((UndoResult.CONFIRMED, interaction))
        self.stop()


class PlanReviewResult(enum.Enum):
    CONFIRMED = "confirmed"
    SKIPPED = "skipped"
    CANCELLED_ALL = "cancelled_all"
    AUTO_REST = "auto_rest"


class PlanReviewView(discord.ui.View):
    def __init__(self, invoker_id: int) -> None:
        super().__init__(timeout=120)
        self.invoker_id = invoker_id
        self._future: asyncio.Future[PlanReviewResult] | None = None

    def _is_invoker(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.invoker_id

    def _get_future(self) -> asyncio.Future[PlanReviewResult]:
        if self._future is None:
            self._future = asyncio.get_running_loop().create_future()
        return self._future

    async def wait_result(self) -> PlanReviewResult:
        fut = self._get_future()
        await self.wait()
        if fut.done():
            return fut.result()
        return PlanReviewResult.CANCELLED_ALL  # timeout = cancel all for safety

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message(
                "Only the message author can use this button.", ephemeral=True
            )
            return
        await interaction.response.defer()
        self._get_future().set_result(PlanReviewResult.CONFIRMED)
        self.stop()

    @discord.ui.button(label="Ignorer", style=discord.ButtonStyle.secondary, emoji="⏭")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button[Any]) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message(
                "Only the message author can use this button.", ephemeral=True
            )
            return
        await interaction.response.defer()
        self._get_future().set_result(PlanReviewResult.SKIPPED)
        self.stop()

    @discord.ui.button(label="Auto-confirm rest", style=discord.ButtonStyle.primary, emoji="⏩")
    async def auto_rest(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message(
                "Only the message author can use this button.", ephemeral=True
            )
            return
        await interaction.response.defer()
        self._get_future().set_result(PlanReviewResult.AUTO_REST)
        self.stop()

    @discord.ui.button(label="Annuler tout", style=discord.ButtonStyle.danger, emoji="🛑")
    async def cancel_all(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message(
                "Only the message author can use this button.", ephemeral=True
            )
            return
        await interaction.response.defer()
        self._get_future().set_result(PlanReviewResult.CANCELLED_ALL)
        self.stop()
