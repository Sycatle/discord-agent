import logging

import discord
from discord.ext import commands

from architect.agent.agent import ArchitectAgent
from architect.agent.providers.base import LLMProvider
from architect.agent.providers.claude import ClaudeProvider
from architect.bot.context_command import ContextCommand
from architect.bot.events import BotEvents
from architect.bot.history import ConversationHistory
from architect.config import settings
from architect.executor.executor import Executor

logger = logging.getLogger(__name__)


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

    async def on_error(self, event_method: str, *args, **kwargs) -> None:
        logger.exception("Erreur non interceptée dans l'event '%s'", event_method)
