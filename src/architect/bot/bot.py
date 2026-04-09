import discord
from discord.ext import commands

from ..config import settings

# TODO: rewrite in step 9 — re-add ArchitectCommands after commands.py is rewritten


class ArchitectBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        guild = discord.Object(id=settings.discord_guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def on_ready(self) -> None:
        print(f"Bot connected: {self.user} (guild_id={settings.discord_guild_id})")

    async def on_disconnect(self) -> None:
        print("Bot disconnected")
    
    async def on_error(self, event_method: str, *args, **kwargs) -> None:
        print(f"Error in event: {event_method}")
        import traceback
        traceback.print_exc()
