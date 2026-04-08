import discord

from ..models.plan import Plan


class ConfirmView(discord.ui.View):
    def __init__(self, plan: Plan, invoker_id: int) -> None:
        super().__init__(timeout=120)
        self.plan = plan
        self.invoker_id = invoker_id
        self.confirmed = False

    def _is_invoker(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.invoker_id

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message(
                "Only the admin who triggered the command can confirm.", ephemeral=True
            )
            return
        await interaction.response.defer()
        self.confirmed = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message(
                "Only the admin who triggered the command can cancel.", ephemeral=True
            )
            return
        self.stop()
        await interaction.response.send_message("Plan cancelled.", ephemeral=True)


def build_plan_embed(plan: Plan) -> discord.Embed:
    embed = discord.Embed(
        title=f"Plan: {plan.title}",
        description=plan.description,
        color=discord.Color.blurple(),
    )
    actions_text = "\n".join(
        f"`{i + 1}.` **{a.type}** — {a.params}"
        for i, a in enumerate(plan.actions)
    )
    embed.add_field(name=f"{len(plan.actions)} action(s)", value=actions_text or "No actions.", inline=False)
    embed.set_footer(text="Confirm or cancel within 120s.")
    return embed
