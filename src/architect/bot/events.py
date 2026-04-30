from __future__ import annotations

import logging

import discord
from discord.ext import commands

from architect.agent.agent import ArchitectAgent
from architect.agent.events import (
    ClarificationEvent,
    ConfirmationRequiredEvent,
    PlanGeneratedEvent,
    ReadOnlyToolEvent,
    ReplyEvent,
)
from architect.bot.history import ConversationHistory
from architect.bot.views import ConfirmResult, ConfirmView, PlanResult, PlanView
from architect.config import settings
from architect.executor.executor import ROLLBACK_ACTIONS, ExecuteError, Executor
from architect.storage.guild_context import GuildContext
from architect.storage.guild_context import load as load_guild_context

logger = logging.getLogger(__name__)

MAX_STEPS = 10

_EMBED_LIMIT = 4000  # 96-char margin for Discord markup


def _make_embed(
    description: str,
    title: str | None = None,
    color: discord.Color = discord.Color.blurple(),
) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


_MAX_ERRORS_DISPLAY = 20


def _chunk_text(text: str, limit: int = _EMBED_LIMIT) -> list[str]:
    """Split text into chunks <= limit. Strategy: paragraphs → lines → hard cut.

    Returns [""] for empty input (intentional: lets callers iterate without branching).
    """
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for para in text.split("\n\n"):
        candidate = current + "\n\n" + para if current else para
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(para) <= limit:
                current = para
            else:
                current = ""
                for line in para.split("\n"):
                    candidate = current + "\n" + line if current else line
                    if len(candidate) <= limit:
                        current = candidate
                    else:
                        if current:
                            chunks.append(current)
                        while len(line) > limit:
                            cut = line.rfind(" ", 0, limit)
                            if cut <= 0:
                                cut = limit  # no whitespace → hard cut
                            chunks.append(line[:cut])
                            line = line[cut:]
                        current = line
    if current:
        chunks.append(current)
    return chunks


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
            await message.reply("What is your request?")
            return

        guild = message.guild
        if guild is None:
            await message.reply("This bot only works inside a Discord server.")
            return
        if guild.id != settings.discord_guild_id:
            await message.reply("This bot is not configured for this server.")
            return

        channel_id = message.channel.id
        self._history.append(channel_id, "user", prompt)

        try:
            channels = await guild.fetch_channels()
        except discord.HTTPException:
            logger.exception("fetch_channels failed for guild %s", guild.id)
            channels = None
        guild_context = _serialize_guild(guild, channels)
        server_context = load_guild_context(guild.id)

        thread_name = prompt[:97] + "..." if len(prompt) > 100 else prompt
        try:
            thread = await message.create_thread(name=thread_name, auto_archive_duration=60)
        except discord.Forbidden:
            thread = message.channel  # fallback without a thread

        status_msg = await thread.send(
            embed=_make_embed("Analyse en cours...", color=discord.Color.orange())
        )

        try:
            await self._run_agent_loop(
                message, thread, status_msg, guild, channel_id, guild_context, server_context
            )
        except Exception:
            logger.exception("agent loop failed for channel %s", channel_id)
            await status_msg.edit(
                embed=_make_embed("An unexpected error occurred.", color=discord.Color.red())
            )

    async def _run_agent_loop(
        self,
        message: discord.Message,
        thread: discord.abc.Messageable,
        status_msg: discord.Message,
        guild: discord.Guild,
        channel_id: int,
        guild_context: str,
        server_context: GuildContext | None = None,
    ) -> None:
        for _ in range(MAX_STEPS):
            history = self._history.get(channel_id)
            # Use plan model on the first step of a fresh conversation (only the user message in history)
            use_plan_model = len(history) == 1
            events = await self._agent.step(
                history, guild_context, server_context=server_context, use_plan_model=use_plan_model
            )

            if not events:
                break

            tool_call_blocks: list[dict] = []
            tool_results: list[tuple[str, str]] = []  # (tool_use_id, result)
            has_tool_calls = False
            stop_loop = False

            for event in events:
                if isinstance(event, ReplyEvent):
                    chunks = _chunk_text(event.text)
                    await status_msg.edit(embed=_make_embed(chunks[0]))
                    for chunk in chunks[1:]:
                        await thread.send(embed=_make_embed(chunk))
                    self._history.append(channel_id, "assistant", event.text)
                    stop_loop = True
                    break

                elif isinstance(event, ClarificationEvent):
                    await status_msg.edit(
                        embed=_make_embed(
                            event.question,
                            title="Clarification needed",
                            color=discord.Color.yellow(),
                        )
                    )
                    self._history.append(channel_id, "assistant", event.question)
                    stop_loop = True
                    break

                elif isinstance(event, ReadOnlyToolEvent):
                    await status_msg.edit(
                        embed=_make_embed(
                            f"Outil en cours : `{event.tool_name}`...", color=discord.Color.orange()
                        )
                    )
                    result = await self._executor.execute(event.tool_name, event.params, guild)
                    tool_call_blocks.append(
                        {
                            "type": "tool_use",
                            "id": event.tool_use_id,
                            "name": event.tool_name,
                            "input": event.params,
                        }
                    )
                    tool_results.append((event.tool_use_id, result))
                    has_tool_calls = True

                elif isinstance(event, ConfirmationRequiredEvent):
                    formatted = _format_params(event.params)
                    view = ConfirmView(invoker_id=message.author.id)
                    await thread.send(
                        embed=_make_embed(
                            formatted, title=f"`{event.tool_name}`", color=discord.Color.orange()
                        ),
                        view=view,
                    )
                    confirm_result = await view.wait_result()

                    tool_call_blocks.append(
                        {
                            "type": "tool_use",
                            "id": event.tool_use_id,
                            "name": event.tool_name,
                            "input": event.params,
                        }
                    )
                    has_tool_calls = True

                    if confirm_result == ConfirmResult.CANCELLED_ALL:
                        await thread.send(
                            embed=_make_embed(
                                "All actions were cancelled.", color=discord.Color.red()
                            )
                        )
                        tool_results.append((event.tool_use_id, "cancelled by user"))
                        stop_loop = True
                    elif confirm_result == ConfirmResult.CANCELLED:
                        tool_results.append((event.tool_use_id, "cancelled by user"))
                    else:  # CONFIRMED
                        executed = await self._executor.execute(
                            event.tool_name, event.params, guild
                        )
                        for chunk in _chunk_text(executed):
                            await thread.send(embed=_make_embed(chunk, color=discord.Color.green()))
                        tool_results.append((event.tool_use_id, executed))

                    if stop_loop:
                        break

                elif isinstance(event, PlanGeneratedEvent):
                    logger.info(
                        "plan generated: %s (%d actions)",
                        event.title,
                        len(event.actions),
                        extra={
                            "event": "plan_generated",
                            "guild_id": guild.id,
                            "channel_id": channel_id,
                            "user_id": message.author.id,
                            "action_count": len(event.actions),
                        },
                    )
                    await status_msg.edit(
                        embed=_make_embed(
                            "Plan generated, awaiting validation...", color=discord.Color.orange()
                        )
                    )
                    plan_view = PlanView(
                        title=event.title,
                        actions=event.actions,
                        invoker_id=message.author.id,
                    )
                    embed, file_content = plan_view.build_embed()

                    if file_content is not None:
                        import io

                        file = discord.File(io.BytesIO(file_content.encode()), filename="plan.txt")
                        await thread.send(embed=embed, file=file, view=plan_view)
                    else:
                        await thread.send(embed=embed, view=plan_view)

                    plan_result = await plan_view.wait_result()

                    if plan_result == PlanResult.CANCELLED:
                        result_str = "Plan cancelled by user."
                        await status_msg.edit(
                            embed=_make_embed(result_str, color=discord.Color.red())
                        )
                    elif plan_result == PlanResult.REVIEW:
                        success, errors = await self._review_batch(
                            event.actions, guild, message.author.id, message, thread
                        )
                        result_str = (
                            f"Review complete: {success}/{len(event.actions)} actions executed."
                        )
                        if errors:
                            displayed_errors = errors[:_MAX_ERRORS_DISPLAY]
                            error_block = "\n".join(f"• {e}" for e in displayed_errors)
                            if len(errors) > _MAX_ERRORS_DISPLAY:
                                error_block += (
                                    f"\n… et {len(errors) - _MAX_ERRORS_DISPLAY} more errors"
                                )
                            result_str += f"\nErreurs :\n{error_block}"
                        color = discord.Color.green() if not errors else discord.Color.orange()
                        await status_msg.edit(embed=_make_embed(result_str, color=color))
                    else:  # CONFIRMED_ALL or CONFIRMED_ATOMIC
                        atomic = plan_result == PlanResult.CONFIRMED_ATOMIC
                        progress_msg = await thread.send(
                            embed=_make_embed(
                                f"Execution in progress... 0/{len(event.actions)}",
                                color=discord.Color.orange(),
                            )
                        )
                        success, errors, rolled_back = await self._execute_batch(
                            event.actions, guild, progress_msg, atomic=atomic
                        )
                        logger.info(
                            "plan executed: %d/%d ok, %d rolled back",
                            success,
                            len(event.actions),
                            rolled_back,
                            extra={
                                "event": "plan_executed",
                                "guild_id": guild.id,
                                "channel_id": channel_id,
                                "user_id": message.author.id,
                                "action_count": len(event.actions),
                                "success": success,
                                "rolled_back": rolled_back,
                                "errors": len(errors),
                            },
                        )
                        result_str = f"{success}/{len(event.actions)} actions executed."
                        if rolled_back:
                            result_str += f"\n{rolled_back} action(s) reverted by atomic rollback."
                        if errors:
                            displayed_errors = errors[:_MAX_ERRORS_DISPLAY]
                            error_block = "\n".join(f"• {e}" for e in displayed_errors)
                            if len(errors) > _MAX_ERRORS_DISPLAY:
                                error_block += (
                                    f"\n… et {len(errors) - _MAX_ERRORS_DISPLAY} more errors"
                                )
                            result_str += f"\nErreurs :\n{error_block}"
                        color = discord.Color.green() if not errors else discord.Color.orange()
                        await status_msg.edit(embed=_make_embed(result_str, color=color))

                    # Add to history as tool_call + result
                    tool_call_blocks.append(
                        {
                            "type": "tool_use",
                            "id": event.tool_use_id,
                            "name": "generate_plan",
                            "input": {"title": event.title, "actions": event.actions},
                        }
                    )
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
        atomic: bool = False,
    ) -> tuple[int, list[str], int]:
        """
        Execute all actions sequentially. Updates progress_msg embed every 5 actions or on errors.

        In atomic=True mode, on the first error the already-performed creations
        are reverted in reverse order (delete_channel, delete_role, etc.) —
        actions without a deterministic inverse (edit_*, delete_*, create_invite)
        are left as-is.

        Returns (success_count, errors, rollback_count).
        """
        success_count = 0
        errors: list[str] = []
        completed: list[dict] = []  # successful actions, in order, for rollback
        total = len(actions)
        stopped_early = False

        for i, action in enumerate(actions, 1):
            action_type = action.get("type", "")
            params = action.get("params", {})
            try:
                await self._executor.execute(action_type, params, guild, strict=True)
                success_count += 1
                completed.append(action)
            except (ExecuteError, ValueError, NotImplementedError) as e:
                logger.exception(
                    "action %s failed in batch",
                    action_type,
                    extra={"event": "action_failed", "tool_name": action_type},
                )
                errors.append(f"{action_type}({params.get('name', '?')}): {e}")
                if atomic:
                    stopped_early = True
                    break
            except Exception as e:
                logger.exception("unexpected error on %s in batch", action_type)
                errors.append(f"{action_type}({params.get('name', '?')}): {e}")
                if atomic:
                    stopped_early = True
                    break

            # Update progress every 5 actions or on last action
            if i % 5 == 0 or i == total:
                status = f"Execution in progress... {i}/{total}"
                if errors:
                    status += f"\n{len(errors)} erreur(s)"
                embed = discord.Embed(description=status, color=discord.Color.orange())
                try:
                    await progress_msg.edit(embed=embed)
                except discord.HTTPException:
                    logger.warning("progress_msg edit failed, continuing")

        rollback_count = 0
        if stopped_early and atomic and completed:
            try:
                await progress_msg.edit(
                    embed=discord.Embed(
                        description=f"Erreur — rollback en cours de {len(completed)} actions...",
                        color=discord.Color.red(),
                    )
                )
            except discord.HTTPException:
                pass
            rollback_count = await self._rollback(completed, guild)

        return success_count - rollback_count, errors, rollback_count

    async def _rollback(self, completed: list[dict], guild: discord.Guild) -> int:
        """Revert creations in reverse order. Return the count of reverted actions."""
        count = 0
        for action in reversed(completed):
            action_type = action.get("type", "")
            params = action.get("params", {})
            inverse = ROLLBACK_ACTIONS.get(action_type)
            if inverse is None:
                continue
            inverse_type, param_map = inverse
            inverse_params = {target: params.get(source) for target, source in param_map.items()}
            if any(v is None for v in inverse_params.values()):
                continue
            try:
                await self._executor.execute(inverse_type, inverse_params, guild, strict=True)
                count += 1
            except Exception:
                logger.exception("rollback failed for %s → %s", action_type, inverse_type)
        return count

    async def _review_batch(
        self,
        actions: list[dict],
        guild: discord.Guild,
        invoker_id: int,
        message: discord.Message,
        thread: discord.abc.Messageable | None = None,
    ) -> tuple[int, list[str]]:
        """
        Review each action one by one using PlanReviewView.
        If AUTO_REST is clicked, switches to _execute_batch for remaining actions.
        Returns (success_count, errors).
        """
        from .views import PlanReviewResult, PlanReviewView

        dest = thread if thread is not None else message.channel
        success_count = 0
        errors: list[str] = []

        for i, action in enumerate(actions):
            action_type = action.get("type", "")
            params = action.get("params", {})
            formatted = _format_params(params)

            view = PlanReviewView(invoker_id=invoker_id)
            await dest.send(
                embed=_make_embed(
                    f"[{i + 1}/{len(actions)}] {formatted}",
                    title=f"`{action_type}`",
                    color=discord.Color.orange(),
                ),
                view=view,
            )
            result = await view.wait_result()

            if result == PlanReviewResult.CANCELLED_ALL:
                await dest.send(embed=_make_embed("Review cancelled.", color=discord.Color.red()))
                break
            elif result == PlanReviewResult.SKIPPED:
                continue
            elif result == PlanReviewResult.AUTO_REST:
                # Execute remaining actions (including current one) in batch
                remaining = actions[i:]
                progress_msg = await dest.send(
                    embed=_make_embed(
                        f"Execution in progress... 0/{len(remaining)}", color=discord.Color.orange()
                    )
                )
                batch_success, batch_errors, _ = await self._execute_batch(
                    remaining, guild, progress_msg
                )
                success_count += batch_success
                errors.extend(batch_errors)
                break
            else:  # CONFIRMED
                try:
                    await self._executor.execute(action_type, params, guild)
                    success_count += 1
                    await dest.send(
                        embed=_make_embed(
                            f"`{action_type}`: {params.get('name', '?')}",
                            color=discord.Color.green(),
                        )
                    )
                except Exception as e:
                    logger.exception("action %s failed during review", action_type)
                    error_msg = f"{action_type}: {e}"
                    errors.append(error_msg)
                    await dest.send(
                        embed=_make_embed(error_msg, title="Erreur", color=discord.Color.red())
                    )

        return success_count, errors
