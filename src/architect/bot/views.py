import asyncio
import enum

import discord


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

    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message("Seul l'auteur peut utiliser ce bouton.", ephemeral=True)
            return
        await interaction.response.defer()
        self._get_future().set_result(ConfirmResult.CONFIRMED)
        self.stop()

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message("Seul l'auteur peut utiliser ce bouton.", ephemeral=True)
            return
        await interaction.response.defer()
        self._get_future().set_result(ConfirmResult.CANCELLED)
        self.stop()

    @discord.ui.button(label="Tout annuler", style=discord.ButtonStyle.danger, emoji="🛑")
    async def cancel_all(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message("Seul l'auteur peut utiliser ce bouton.", ephemeral=True)
            return
        await interaction.response.defer()
        self._get_future().set_result(ConfirmResult.CANCELLED_ALL)
        self.stop()


class PlanResult(enum.Enum):
    CONFIRMED_ALL = "confirmed_all"
    CONFIRMED_ATOMIC = "confirmed_atomic"
    REVIEW = "review"
    CANCELLED = "cancelled"


class PlanView(discord.ui.View):
    def __init__(self, title: str, actions: list[dict], invoker_id: int) -> None:
        super().__init__(timeout=300)
        self.title = title
        self.actions = actions
        self.invoker_id = invoker_id
        self._future: asyncio.Future[PlanResult] | None = None

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
        """
        Returns (embed, file_content_or_none).
        If the plan is too long for an embed (> 5500 chars total), returns a minimal embed
        and the full plan as a string to be sent as a file attachment.
        """
        from collections import Counter
        type_counts = Counter(a.get("type", "unknown") for a in self.actions)

        # Build summary line — group by domain so 27+ ActionTypes stay readable
        domain_buckets = {
            "créations": (
                "create_category", "create_text_channel", "create_voice_channel",
                "create_forum_channel", "create_stage_channel", "create_role",
                "create_invite", "create_webhook", "create_scheduled_event",
                "create_automod_rule",
            ),
            "modifications": (
                "edit_channel", "edit_role", "edit_member", "edit_webhook",
                "edit_scheduled_event", "edit_automod_rule", "edit_server",
                "edit_welcome_screen", "set_channel_permissions",
                "assign_role", "remove_role",
            ),
            "suppressions": (
                "delete_channel", "delete_invite", "delete_webhook",
                "delete_role", "delete_scheduled_event", "delete_automod_rule",
            ),
        }
        count_parts = []
        for label, types in domain_buckets.items():
            count = sum(type_counts.get(t, 0) for t in types)
            if count > 0:
                count_parts.append(f"**{count}** {label}")
        unknown = sum(c for t, c in type_counts.items() if not any(t in types for types in domain_buckets.values()))
        if unknown:
            count_parts.append(f"**{unknown}** autres")
        summary = " · ".join(count_parts) if count_parts else "Aucune action"

        embed = discord.Embed(
            title=f"📋 Plan — {self.title}",
            description=summary,
            color=discord.Color.blurple(),
        )

        # Group actions by category for display
        # Show up to 10 actions inline, truncate the rest
        action_lines = []
        for action in self.actions[:10]:
            atype = action.get("type", "?")
            params = action.get("params", {})
            name = params.get("name", params.get("channel", "?"))
            action_lines.append(f"• `{atype}`: {name}")
        if len(self.actions) > 10:
            action_lines.append(f"… et {len(self.actions) - 10} autres actions")

        embed.add_field(name="Actions", value="\n".join(action_lines) or "—", inline=False)
        embed.set_footer(text=f"{len(self.actions)} actions au total")

        # Check if we need to fallback to file
        # Rough length check: if more than 30 actions, offer file too
        file_content = None
        if len(self.actions) > 30:
            lines = [f"# Plan: {self.title}", f"Total: {len(self.actions)} actions", ""]
            for i, action in enumerate(self.actions, 1):
                atype = action.get("type", "?")
                params = action.get("params", {})
                lines.append(f"{i}. {atype}: {params}")
            file_content = "\n".join(lines)

        return embed, file_content

    @discord.ui.button(label="Tout confirmer", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_all(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message("Seul l'auteur peut utiliser ce bouton.", ephemeral=True)
            return
        await interaction.response.defer()
        self._get_future().set_result(PlanResult.CONFIRMED_ALL)
        self.stop()

    @discord.ui.button(label="Atomic (rollback si erreur)", style=discord.ButtonStyle.primary, emoji="⚛")
    async def confirm_atomic(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message("Seul l'auteur peut utiliser ce bouton.", ephemeral=True)
            return
        await interaction.response.defer()
        self._get_future().set_result(PlanResult.CONFIRMED_ATOMIC)
        self.stop()

    @discord.ui.button(label="Réviser", style=discord.ButtonStyle.secondary, emoji="🔍")
    async def review(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message("Seul l'auteur peut utiliser ce bouton.", ephemeral=True)
            return
        await interaction.response.defer()
        self._get_future().set_result(PlanResult.REVIEW)
        self.stop()

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message("Seul l'auteur peut utiliser ce bouton.", ephemeral=True)
            return
        await interaction.response.defer()
        self._get_future().set_result(PlanResult.CANCELLED)
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

    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message("Seul l'auteur peut utiliser ce bouton.", ephemeral=True)
            return
        await interaction.response.defer()
        self._get_future().set_result(PlanReviewResult.CONFIRMED)
        self.stop()

    @discord.ui.button(label="Ignorer", style=discord.ButtonStyle.secondary, emoji="⏭")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message("Seul l'auteur peut utiliser ce bouton.", ephemeral=True)
            return
        await interaction.response.defer()
        self._get_future().set_result(PlanReviewResult.SKIPPED)
        self.stop()

    @discord.ui.button(label="Auto-confirmer le reste", style=discord.ButtonStyle.primary, emoji="⏩")
    async def auto_rest(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message("Seul l'auteur peut utiliser ce bouton.", ephemeral=True)
            return
        await interaction.response.defer()
        self._get_future().set_result(PlanReviewResult.AUTO_REST)
        self.stop()

    @discord.ui.button(label="Annuler tout", style=discord.ButtonStyle.danger, emoji="🛑")
    async def cancel_all(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message("Seul l'auteur peut utiliser ce bouton.", ephemeral=True)
            return
        await interaction.response.defer()
        self._get_future().set_result(PlanReviewResult.CANCELLED_ALL)
        self.stop()
