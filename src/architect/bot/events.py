from __future__ import annotations

import discord
from discord.ext import commands

from architect.agent.agent import ArchitectAgent
from architect.config import settings
from architect.agent.events import (
    ClarificationEvent,
    ConfirmationRequiredEvent,
    ReadOnlyToolEvent,
    ReplyEvent,
)
from architect.bot.history import ConversationHistory
from architect.bot.views import ConfirmResult, ConfirmView
from architect.executor.executor import Executor

MAX_STEPS = 10


def _serialize_guild(guild: discord.Guild, channels=None) -> str:
    all_channels = channels if channels is not None else guild.channels
    categories = [c for c in all_channels if isinstance(c, discord.CategoryChannel)]
    text_channels = [c for c in all_channels if isinstance(c, discord.TextChannel)]
    voice_channels = [c for c in all_channels if isinstance(c, discord.VoiceChannel)]
    lines = [
        f"Categories: {', '.join(c.name for c in categories) or 'none'}",
        f"Text channels: {', '.join('#' + c.name for c in text_channels) or 'none'}",
        f"Voice channels: {', '.join(c.name for c in voice_channels) or 'none'}",
        f"Roles: {', '.join(r.name for r in guild.roles if r.name != '@everyone') or 'none'}",
    ]
    return "\n".join(lines)


def _format_params(params: dict) -> str:
    parts = []
    for key, value in params.items():
        if isinstance(value, list):
            parts.append(f"{key}: [{', '.join(str(v) for v in value)}]")
        else:
            parts.append(f"{key}: {value}")
    return ", ".join(parts)


class BotEvents(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        agent: ArchitectAgent,
        executor: Executor,
        history: ConversationHistory,
    ) -> None:
        self.bot = bot
        self._agent = agent
        self._executor = executor
        self._history = history

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        is_mention = self.bot.user in message.mentions
        is_reply_to_bot = (
            message.reference is not None
            and message.reference.resolved is not None
            and isinstance(message.reference.resolved, discord.Message)
            and message.reference.resolved.author == self.bot.user
        )

        if not (is_mention or is_reply_to_bot):
            return

        prompt = message.content
        if self.bot.user:
            prompt = prompt.replace(f"<@{self.bot.user.id}>", "").strip()

        if not prompt:
            await message.reply("Quelle est ta demande ?")
            return

        guild = message.guild
        if guild is None:
            await message.reply("Ce bot fonctionne uniquement dans un serveur Discord.")
            return
        if guild.id != settings.discord_guild_id:
            return

        channel_id = message.channel.id
        self._history.append(channel_id, "user", prompt)

        try:
            channels = await guild.fetch_channels()
        except Exception:
            channels = None
        guild_context = _serialize_guild(guild, channels)

        await self._run_agent_loop(message, guild, channel_id, guild_context)

    async def _run_agent_loop(
        self,
        message: discord.Message,
        guild: discord.Guild,
        channel_id: int,
        guild_context: str,
    ) -> None:
        for _ in range(MAX_STEPS):
            events = await self._agent.step(self._history.get(channel_id), guild_context)

            if not events:
                break

            tool_call_blocks: list[dict] = []
            tool_results: list[tuple[str, str]] = []  # (tool_use_id, result)
            has_tool_calls = False
            stop_loop = False

            for event in events:
                if isinstance(event, ReplyEvent):
                    await message.channel.send(event.text)
                    self._history.append(channel_id, "assistant", event.text)
                    stop_loop = True
                    break

                elif isinstance(event, ClarificationEvent):
                    await message.channel.send(event.question)
                    self._history.append(channel_id, "assistant", event.question)
                    stop_loop = True
                    break

                elif isinstance(event, ReadOnlyToolEvent):
                    await message.channel.send(f"🔍 `{event.tool_name}`...")
                    result = await self._executor.execute(event.tool_name, event.params, guild)
                    tool_call_blocks.append({
                        "type": "tool_use",
                        "id": event.tool_use_id,
                        "name": event.tool_name,
                        "input": event.params,
                    })
                    tool_results.append((event.tool_use_id, result))
                    has_tool_calls = True

                elif isinstance(event, ConfirmationRequiredEvent):
                    formatted = _format_params(event.params)
                    view = ConfirmView(invoker_id=message.author.id)
                    await message.channel.send(
                        f"🔧 **{event.tool_name}** — {formatted}",
                        view=view,
                    )
                    confirm_result = await view.wait_result()

                    tool_call_blocks.append({
                        "type": "tool_use",
                        "id": event.tool_use_id,
                        "name": event.tool_name,
                        "input": event.params,
                    })
                    has_tool_calls = True

                    if confirm_result == ConfirmResult.CANCELLED_ALL:
                        await message.channel.send("Toutes les actions ont été annulées.")
                        tool_results.append((event.tool_use_id, "cancelled by user"))
                        stop_loop = True
                    elif confirm_result == ConfirmResult.CANCELLED:
                        tool_results.append((event.tool_use_id, "cancelled by user"))
                    else:  # CONFIRMED
                        executed = await self._executor.execute(event.tool_name, event.params, guild)
                        await message.channel.send(f"✅ {executed}")
                        tool_results.append((event.tool_use_id, executed))

                    if stop_loop:
                        break

            # Flush tool calls + results to history in the correct Anthropic order
            if has_tool_calls:
                self._history.append_assistant_tool_calls(channel_id, tool_call_blocks)
                for tool_use_id, result in tool_results:
                    self._history.append_tool_result(channel_id, tool_use_id, result)

            if stop_loop or not has_tool_calls:
                break
