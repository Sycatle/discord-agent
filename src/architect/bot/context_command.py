from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from architect.storage.guild_context import GuildContext, load, save


class ContextModal(discord.ui.Modal, title="Server context"):
    def __init__(self, existing: GuildContext | None) -> None:
        super().__init__()
        self.name_input: discord.ui.TextInput[ContextModal] = discord.ui.TextInput(
            label="Server name / description",
            style=discord.TextStyle.paragraph,
            required=False,
            default=existing.name if existing else "",
            max_length=1000,
        )
        self.objectives_input: discord.ui.TextInput[ContextModal] = discord.ui.TextInput(
            label="Goals & use cases",
            style=discord.TextStyle.paragraph,
            required=False,
            default=existing.objectives if existing else "",
            max_length=1000,
        )
        self.tone_input: discord.ui.TextInput[ContextModal] = discord.ui.TextInput(
            label="Desired tone & style",
            style=discord.TextStyle.paragraph,
            required=False,
            default=existing.tone if existing else "",
            max_length=500,
        )
        self.rules_input: discord.ui.TextInput[ContextModal] = discord.ui.TextInput(
            label="Rules & constraints",
            style=discord.TextStyle.paragraph,
            required=False,
            default=existing.rules if existing else "",
            max_length=1000,
        )
        self.add_item(self.name_input)
        self.add_item(self.objectives_input)
        self.add_item(self.tone_input)
        self.add_item(self.rules_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            return
        ctx = GuildContext(
            guild_id=interaction.guild_id,
            name=self.name_input.value,
            objectives=self.objectives_input.value,
            tone=self.tone_input.value,
            rules=self.rules_input.value,
        )
        save(ctx)
        embed = discord.Embed(
            title="Context saved",
            description="The server context has been updated. The agent will use it on the next interaction.",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ContextCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    context_group = app_commands.Group(
        name="context",
        description="Manage server context used by the AI agent",
    )

    @context_group.command(name="set", description="Set the server context (admin only)")
    async def context_set(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command must be used inside a server.", ephemeral=True
            )
            return
        # In a guild context, interaction.user is always a discord.Member which has
        # guild_permissions; the User branch of the union doesn't apply at runtime.
        guild_perms = getattr(interaction.user, "guild_permissions", None)
        if guild_perms is None or not guild_perms.manage_guild:
            await interaction.response.send_message(
                "Required permission: **Manage Server**.", ephemeral=True
            )
            return
        existing = load(interaction.guild_id)
        await interaction.response.send_modal(ContextModal(existing=existing))

    @context_group.command(name="show", description="Show the current server context")
    async def context_show(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command must be used inside a server.", ephemeral=True
            )
            return
        ctx = load(interaction.guild_id)
        if ctx is None:
            await interaction.response.send_message(
                "No context defined. Use `/context set` to create one.",
                ephemeral=True,
            )
            return
        embed = discord.Embed(title="Server context", color=discord.Color.blurple())
        embed.add_field(name="Name / description", value=ctx.name or "*not set*", inline=False)
        embed.add_field(name="Goals", value=ctx.objectives or "*not set*", inline=False)
        embed.add_field(name="Tone & style", value=ctx.tone or "*not set*", inline=False)
        embed.add_field(name="Rules", value=ctx.rules or "*not set*", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
