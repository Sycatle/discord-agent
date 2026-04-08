import discord
from discord import app_commands
from discord.ext import commands

from ..agent.agent import ArchitectAgent
from ..executor.executor import Executor
from .views import ConfirmView, build_plan_embed


class ArchitectCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.agent = ArchitectAgent()
        self.executor = Executor()

    @app_commands.command(
        name="architect",
        description="Generate and execute a Discord configuration plan.",
    )
    @app_commands.describe(prompt="Describe the channels, categories and roles to create")
    @app_commands.default_permissions(administrator=True)
    async def architect(self, interaction: discord.Interaction, prompt: str) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            plan = await self.agent.generate_plan(prompt)
        except Exception as e:
            await interaction.followup.send(
                f"Error generating plan: {e}", ephemeral=True
            )
            return

        embed = build_plan_embed(plan)
        view = ConfirmView(plan, invoker_id=interaction.user.id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        await view.wait()

        if not view.confirmed:
            return

        if interaction.guild is None:
            await interaction.followup.send(
                "This command must be used inside a server.", ephemeral=True
            )
            return

        try:
            results = await self.executor.execute(plan, interaction.guild)
            summary = "\n".join(f"✅ {r}" for r in results)
            await interaction.followup.send(f"**Plan executed:**\n{summary}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(
                f"Error during execution: {e}", ephemeral=True
            )
