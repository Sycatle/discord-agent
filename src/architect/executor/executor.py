"""Thin dispatcher around the handler registry.

``Executor.execute`` is the single public entry point. It:

1. Looks up the handler spec for ``tool_name`` in the registry.
2. Validates the raw params dict via the spec's Pydantic model.
3. Pre-checks the bot's permission for mutating tools.
4. Awaits the handler.
5. Wraps Discord errors into readable messages, optionally re-raising as
   ``ExecuteError`` in strict mode (used by the atomic batch coordinator).
"""

from __future__ import annotations

import logging
from typing import Any

import discord
from pydantic import ValidationError

from architect.executor.handlers import HANDLERS
from architect.executor.rollback import ROLLBACK_ACTIONS

__all__ = ["ROLLBACK_ACTIONS", "ExecuteError", "Executor"]

logger = logging.getLogger(__name__)


class ExecuteError(Exception):
    """Business error (missing permission, Discord 403/404/HTTPException).

    Raised by ``execute(strict=True)`` so the batch coordinator can distinguish
    success from failure — the non-strict mode returns the message as a string
    to stay compatible with the agentic loop.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Executor:
    async def execute(
        self,
        tool_name: str,
        params: dict[str, Any],
        guild: discord.Guild,
        *,
        strict: bool = False,
    ) -> str:
        """Execute a single tool call and return a result string.

        Wraps Discord API errors (Forbidden/NotFound/HTTPException) into
        readable messages and pre-checks bot permissions for mutating tools.

        In ``strict=True`` mode, Discord and permission errors are raised as
        ``ExecuteError`` instead of being returned as a string — used by the
        atomic batch coordinator to count failures correctly.
        """
        spec = HANDLERS.get(tool_name)
        if spec is None:
            raise NotImplementedError(f"No handler for tool: {tool_name!r}")

        if spec.required_permission is not None and guild.me is not None:
            if not getattr(guild.me.guild_permissions, spec.required_permission, False):
                msg = (
                    f"Missing permission: `{spec.required_permission}`. "
                    f"The bot cannot execute `{tool_name}`."
                )
                if strict:
                    raise ExecuteError(msg)
                return msg

        try:
            validated = spec.params_model.model_validate(params)
        except ValidationError as e:
            msg = f"Invalid parameters for `{tool_name}`: {e.errors(include_url=False)}"
            if strict:
                raise ExecuteError(msg) from e
            return msg

        try:
            return await spec.handler(validated, guild)
        except discord.Forbidden as e:
            logger.warning("Discord Forbidden on %s: %s", tool_name, e)
            msg = f"Action refused by Discord (permissions or role hierarchy): `{tool_name}`."
            if strict:
                raise ExecuteError(msg) from e
            return msg
        except discord.NotFound as e:
            logger.warning("Discord NotFound on %s: %s", tool_name, e)
            msg = (
                f"Entity not found (possibly deleted between preview and execution): `{tool_name}`."
            )
            if strict:
                raise ExecuteError(msg) from e
            return msg
        except discord.HTTPException as e:
            logger.exception("Discord HTTPException on %s", tool_name)
            msg = f"Discord error ({e.status}) on `{tool_name}`: {e.text or e}"
            if strict:
                raise ExecuteError(msg) from e
            return msg
