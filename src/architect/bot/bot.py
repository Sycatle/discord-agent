import discord
from discord.ext import commands

from ..config import settings
from ..agent.agent import ArchitectAgent
from ..agent.providers.base import LLMProvider
from ..agent.providers.claude import ClaudeProvider
from ..executor.executor import Executor
from ..bot.events import BotEvents
from ..bot.history import ConversationHistory
from ..bot.context_command import ContextCommand


class ArchitectBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True  # required to read message content
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        # Instantiate plan_provider if using Claude
        plan_provider: LLMProvider | None = None
        if settings.llm_provider == "claude":
            plan_provider = ClaudeProvider(
                api_key=settings.llm_api_key,
                model=settings.llm_plan_model or settings.llm_model,
            )

        agent = ArchitectAgent(plan_provider=plan_provider)
        executor = Executor()
        history = ConversationHistory()
        await self.add_cog(BotEvents(self, agent, executor, history))
        await self.add_cog(ContextCommand(self))
        guild = discord.Object(id=settings.discord_guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def on_ready(self) -> None:
        print(f"Bot connected: {self.user} (guild_id={settings.discord_guild_id})")
