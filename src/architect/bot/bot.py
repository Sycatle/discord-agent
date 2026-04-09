import discord
from discord.ext import commands

from ..config import settings
from ..agent.agent import ArchitectAgent
from ..executor.executor import Executor
from ..bot.events import BotEvents
from ..bot.history import ConversationHistory


class ArchitectBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True  # required to read message content
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        agent = ArchitectAgent()
        executor = Executor()
        history = ConversationHistory()
        await self.add_cog(BotEvents(self, agent, executor, history))

    async def on_ready(self) -> None:
        print(f"Bot connected: {self.user} (guild_id={settings.discord_guild_id})")
