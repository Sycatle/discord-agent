import discord
from discord.ext import commands

from ..config import settings
from .commands import ArchitectCommands


class ArchitectBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        await self.add_cog(ArchitectCommands(self))
        guild = discord.Object(id=settings.discord_guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def on_ready(self) -> None:
        print(f"Bot connecté : {self.user} (guild_id={settings.discord_guild_id})")
