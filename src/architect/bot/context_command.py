from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from architect.storage.guild_context import GuildContext, load, save


class ContextModal(discord.ui.Modal, title="Contexte du serveur"):
    def __init__(self, existing: GuildContext | None) -> None:
        super().__init__()
        self.name_input = discord.ui.TextInput(
            label="Nom / description du serveur",
            style=discord.TextStyle.paragraph,
            required=False,
            default=existing.name if existing else "",
            max_length=1000,
        )
        self.objectives_input = discord.ui.TextInput(
            label="Objectifs & use cases",
            style=discord.TextStyle.paragraph,
            required=False,
            default=existing.objectives if existing else "",
            max_length=1000,
        )
        self.tone_input = discord.ui.TextInput(
            label="Ton & style souhaité",
            style=discord.TextStyle.paragraph,
            required=False,
            default=existing.tone if existing else "",
            max_length=500,
        )
        self.rules_input = discord.ui.TextInput(
            label="Règles & contraintes",
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
            title="Contexte enregistré",
            description="Le contexte du serveur a été mis à jour. Il sera utilisé par l'agent dès la prochaine interaction.",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ContextCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    context_group = app_commands.Group(
        name="context",
        description="Gérer le contexte du serveur pour l'agent IA",
    )

    @context_group.command(name="set", description="Définir le contexte du serveur (admin)")
    async def context_set(self, interaction: discord.Interaction) -> None:
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "Permission requise : **Gérer le serveur**.", ephemeral=True
            )
            return
        existing = load(interaction.guild_id)
        await interaction.response.send_modal(ContextModal(existing=existing))

    @context_group.command(name="show", description="Afficher le contexte actuel du serveur")
    async def context_show(self, interaction: discord.Interaction) -> None:
        ctx = load(interaction.guild_id)
        if ctx is None:
            await interaction.response.send_message(
                "Aucun contexte défini. Utilisez `/context set` pour en créer un.",
                ephemeral=True,
            )
            return
        embed = discord.Embed(title="Contexte du serveur", color=discord.Color.blurple())
        embed.add_field(name="Nom / description", value=ctx.name or "*non renseigné*", inline=False)
        embed.add_field(name="Objectifs", value=ctx.objectives or "*non renseigné*", inline=False)
        embed.add_field(name="Ton & style", value=ctx.tone or "*non renseigné*", inline=False)
        embed.add_field(name="Règles", value=ctx.rules or "*non renseigné*", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
