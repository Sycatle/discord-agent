from __future__ import annotations

import discord
from discord.ext import commands

from architect.agent.agent import ArchitectAgent
from architect.config import settings
from architect.agent.events import (
    ClarificationEvent,
    ConfirmationRequiredEvent,
    PlanGeneratedEvent,
    ReadOnlyToolEvent,
    ReplyEvent,
)
from architect.bot.history import ConversationHistory
from architect.bot.views import ConfirmResult, ConfirmView, PlanResult, PlanView
from architect.executor.executor import Executor
from architect.storage.guild_context import GuildContext, load as load_guild_context

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
        server_context = load_guild_context(guild.id)

        async with message.channel.typing():
            await self._run_agent_loop(message, guild, channel_id, guild_context, server_context)

    async def _run_agent_loop(
        self,
        message: discord.Message,
        guild: discord.Guild,
        channel_id: int,
        guild_context: str,
        server_context: GuildContext | None = None,
    ) -> None:
        for _ in range(MAX_STEPS):
            history = self._history.get(channel_id)
            # Use plan model on the first step of a fresh conversation (only the user message in history)
            use_plan_model = len(history) == 1
            events = await self._agent.step(history, guild_context, server_context=server_context, use_plan_model=use_plan_model)

            if not events:
                break

            tool_call_blocks: list[dict] = []
            tool_results: list[tuple[str, str]] = []  # (tool_use_id, result)
            has_tool_calls = False
            stop_loop = False

            for event in events:
                if isinstance(event, ReplyEvent):
                    await message.reply(event.text)
                    self._history.append(channel_id, "assistant", event.text)
                    stop_loop = True
                    break

                elif isinstance(event, ClarificationEvent):
                    await message.reply(event.question)
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

                elif isinstance(event, PlanGeneratedEvent):
                    # Build and send the plan embed
                    plan_view = PlanView(
                        title=event.title,
                        actions=event.actions,
                        invoker_id=message.author.id,
                    )
                    embed, file_content = plan_view.build_embed()

                    if file_content is not None:
                        import io
                        file = discord.File(io.BytesIO(file_content.encode()), filename="plan.txt")
                        await message.channel.send(embed=embed, file=file, view=plan_view)
                    else:
                        await message.channel.send(embed=embed, view=plan_view)

                    plan_result = await plan_view.wait_result()

                    if plan_result == PlanResult.CANCELLED:
                        result_str = "Plan annulé par l'utilisateur."
                        await message.channel.send(result_str)
                    elif plan_result == PlanResult.REVIEW:
                        success, errors = await self._review_batch(
                            event.actions, guild, message.author.id, message
                        )
                        result_str = f"Révision terminée : {success}/{len(event.actions)} actions exécutées."
                        if errors:
                            result_str += f"\nErreurs :\n" + "\n".join(f"• {e}" for e in errors)
                        await message.channel.send(result_str)
                    else:  # CONFIRMED_ALL
                        progress_msg = await message.channel.send(
                            embed=discord.Embed(
                                description=f"⚙️ Exécution en cours... 0/{len(event.actions)}",
                                color=discord.Color.orange(),
                            )
                        )
                        success, errors = await self._execute_batch(event.actions, guild, progress_msg)
                        result_str = f"✅ {success}/{len(event.actions)} actions exécutées."
                        if errors:
                            result_str += f"\nErreurs :\n" + "\n".join(f"• {e}" for e in errors)
                        # Update final embed
                        color = discord.Color.green() if not errors else discord.Color.orange()
                        await progress_msg.edit(embed=discord.Embed(description=result_str, color=color))

                    # Add to history as tool_call + result
                    tool_call_blocks.append({
                        "type": "tool_use",
                        "id": event.tool_use_id,
                        "name": "generate_plan",
                        "input": {"title": event.title, "actions": event.actions},
                    })
                    tool_results.append((event.tool_use_id, result_str))
                    has_tool_calls = True
                    stop_loop = True
                    break

            # Flush tool calls + results to history in the correct Anthropic order
            if has_tool_calls:
                self._history.append_assistant_tool_calls(channel_id, tool_call_blocks)
                for tool_use_id, result in tool_results:
                    self._history.append_tool_result(channel_id, tool_use_id, result)

            if stop_loop or not has_tool_calls:
                break

    async def _execute_batch(
        self,
        actions: list[dict],
        guild: discord.Guild,
        progress_msg: discord.Message,
    ) -> tuple[int, list[str]]:
        """
        Execute all actions sequentially. Updates progress_msg embed every 5 actions or on errors.
        Returns (success_count, errors).
        """
        success_count = 0
        errors: list[str] = []
        total = len(actions)

        for i, action in enumerate(actions, 1):
            action_type = action.get("type", "")
            params = action.get("params", {})
            try:
                await self._executor.execute(action_type, params, guild)
                success_count += 1
            except Exception as e:
                errors.append(f"{action_type}({params.get('name', '?')}): {e}")

            # Update progress every 5 actions or on last action
            if i % 5 == 0 or i == total:
                status = f"⚙️ Exécution en cours... {i}/{total}"
                if errors:
                    status += f"\n⚠️ {len(errors)} erreur(s)"
                embed = discord.Embed(description=status, color=discord.Color.orange())
                try:
                    await progress_msg.edit(embed=embed)
                except Exception:
                    pass  # don't fail if edit fails

        return success_count, errors

    async def _review_batch(
        self,
        actions: list[dict],
        guild: discord.Guild,
        invoker_id: int,
        message: discord.Message,
    ) -> tuple[int, list[str]]:
        """
        Review each action one by one using PlanReviewView.
        If AUTO_REST is clicked, switches to _execute_batch for remaining actions.
        Returns (success_count, errors).
        """
        from .views import PlanReviewResult, PlanReviewView

        success_count = 0
        errors: list[str] = []

        for i, action in enumerate(actions):
            action_type = action.get("type", "")
            params = action.get("params", {})
            formatted = _format_params(params)

            view = PlanReviewView(invoker_id=invoker_id)
            await message.channel.send(
                f"🔧 [{i+1}/{len(actions)}] **{action_type}** — {formatted}",
                view=view,
            )
            result = await view.wait_result()

            if result == PlanReviewResult.CANCELLED_ALL:
                await message.channel.send("Révision annulée.")
                break
            elif result == PlanReviewResult.SKIPPED:
                continue
            elif result == PlanReviewResult.AUTO_REST:
                # Execute remaining actions (including current one) in batch
                remaining = actions[i:]
                progress_msg = await message.channel.send(
                    embed=discord.Embed(description=f"⚙️ Exécution en cours... 0/{len(remaining)}", color=discord.Color.orange())
                )
                batch_success, batch_errors = await self._execute_batch(remaining, guild, progress_msg)
                success_count += batch_success
                errors.extend(batch_errors)
                break
            else:  # CONFIRMED
                try:
                    await self._executor.execute(action_type, params, guild)
                    success_count += 1
                    await message.channel.send(f"✅ {action_type}: {params.get('name', '?')}")
                except Exception as e:
                    error_msg = f"{action_type}: {e}"
                    errors.append(error_msg)
                    await message.channel.send(f"❌ {error_msg}")

        return success_count, errors
