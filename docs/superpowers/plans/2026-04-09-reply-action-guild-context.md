# Reply Action + Guild Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow the bot to answer read queries (e.g. "list channels") by passing live guild state to the LLM and introducing a `reply` action type that returns text instead of modifying Discord.

**Architecture:** Add `ActionType.REPLY` to the enum and a no-op executor handler that surfaces its `message` param as the result string. Serialize the guild's channels/roles/categories in the bot command and inject them into the user prompt so the LLM has real data to work with. Update the agent system prompt to document the `reply` action type with a concrete example.

**Tech Stack:** Python 3.12, discord.py 2.x, Pydantic v2, pytest-asyncio

---

## File Map

| File | Change |
|------|--------|
| `src/architect/models/actions.py` | Add `REPLY = "reply"` to `ActionType` |
| `src/architect/executor/executor.py` | Add `REPLY` handler, fix color parsing |
| `src/architect/agent/agent.py` | Add `reply` example to `_PLAN_EXAMPLE`, fix color in example, update `generate_plan` signature |
| `src/architect/bot/commands.py` | Add `_serialize_guild()`, pass context to agent |
| `tests/test_executor.py` | Add test for `REPLY` action |
| `tests/test_agent.py` | Add test for plan with `reply` action |

---

### Task 1: Add REPLY to ActionType

**Files:**
- Modify: `src/architect/models/actions.py`

- [ ] **Step 1: Add REPLY to the enum**

Edit `src/architect/models/actions.py`:

```python
from enum import StrEnum
from typing import Any
from pydantic import BaseModel


class ActionType(StrEnum):
    CREATE_CATEGORY = "create_category"
    CREATE_TEXT_CHANNEL = "create_text_channel"
    CREATE_VOICE_CHANNEL = "create_voice_channel"
    CREATE_ROLE = "create_role"
    SET_CHANNEL_PERMISSIONS = "set_channel_permissions"
    REPLY = "reply"


class Action(BaseModel):
    type: ActionType
    params: dict[str, Any]
```

- [ ] **Step 2: Run existing tests to confirm no regression**

```bash
uv run pytest tests/test_models.py -v
```
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add src/architect/models/actions.py
git commit -m "feat(models): add REPLY action type"
```

---

### Task 2: Add REPLY handler to executor

**Files:**
- Modify: `src/architect/executor/executor.py`
- Test: `tests/test_executor.py`

- [ ] **Step 1: Write the failing test**

Add at the end of `tests/test_executor.py`:

```python
async def test_execute_reply():
    guild = _make_guild()
    plan = Plan(
        title="T", description="D",
        actions=[Action(type=ActionType.REPLY, params={"message": "Here are the channels: #general"})]
    )
    results = await Executor().execute(plan, guild)
    assert results == ["Here are the channels: #general"]
    # Reply must not mutate the guild
    guild.create_category.assert_not_called()
    guild.create_text_channel.assert_not_called()
    guild.create_role.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_executor.py::test_execute_reply -v
```
Expected: FAIL — `NotImplementedError: No handler for action type: reply`

- [ ] **Step 3: Add REPLY handler in executor**

In `src/architect/executor/executor.py`, add the REPLY case to `_dispatch` (before the `case _:` fallback), and fix the color parsing which currently crashes when the LLM sends an integer:

```python
import discord

from ..models.actions import Action, ActionType
from ..models.plan import Plan


class Executor:
    async def execute(self, plan: Plan, guild: discord.Guild) -> list[str]:
        results = []
        for action in plan.actions:
            result = await self._dispatch(action, guild)
            results.append(result)
        return results

    async def _dispatch(self, action: Action, guild: discord.Guild) -> str:
        p = action.params
        match action.type:
            case ActionType.REPLY:
                return str(p["message"])

            case ActionType.CREATE_CATEGORY:
                cat = await guild.create_category(name=p["name"])
                return f"Category created: {cat.name}"

            case ActionType.CREATE_TEXT_CHANNEL:
                category = discord.utils.get(guild.categories, name=p.get("category"))
                ch = await guild.create_text_channel(name=p["name"], category=category)
                return f"Text channel created: #{ch.name}"

            case ActionType.CREATE_VOICE_CHANNEL:
                category = discord.utils.get(guild.categories, name=p.get("category"))
                ch = await guild.create_voice_channel(name=p["name"], category=category)
                return f"Voice channel created: {ch.name}"

            case ActionType.CREATE_ROLE:
                raw_color = p.get("color", 0)
                if isinstance(raw_color, str):
                    color_int = int(raw_color.lstrip("#"), 16)
                else:
                    color_int = int(raw_color)
                role = await guild.create_role(
                    name=p["name"],
                    color=discord.Color(color_int),
                    mentionable=p.get("mentionable", False),
                )
                return f"Role created: @{role.name}"

            case ActionType.SET_CHANNEL_PERMISSIONS:
                channel = discord.utils.get(guild.channels, name=p["channel"])
                role = discord.utils.get(guild.roles, name=p["role"])
                if channel is None:
                    raise ValueError(f"Channel '{p['channel']}' not found in guild")
                if role is None:
                    raise ValueError(f"Role '{p['role']}' not found in guild")
                overwrite = discord.PermissionOverwrite(**p.get("permissions", {}))
                await channel.set_permissions(role, overwrite=overwrite)
                return f"Permissions set: #{p['channel']} → @{p['role']}"

            case _:
                raise NotImplementedError(f"No handler for action type: {action.type}")
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_executor.py -v
```
Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/architect/executor/executor.py tests/test_executor.py
git commit -m "feat(executor): add REPLY handler, fix color parsing"
```

---

### Task 3: Update agent system prompt + generate_plan signature

**Files:**
- Modify: `src/architect/agent/agent.py`
- Test: `tests/test_agent.py`

- [ ] **Step 1: Write the failing test**

Add at the end of `tests/test_agent.py`:

```python
REPLY_PLAN_JSON = json.dumps({
    "title": "Channel List",
    "description": "Lists current channels",
    "actions": [
        {"type": "reply", "params": {"message": "Text channels: #general, #welcome"}}
    ],
})


async def test_generate_plan_with_guild_context():
    from architect.agent.agent import ArchitectAgent
    with patch("architect.agent.agent._build_provider", return_value=MockProvider(REPLY_PLAN_JSON)):
        agent = ArchitectAgent()
    plan = await agent.generate_plan("list channels", guild_context="Text channels: #general, #welcome")
    assert plan.actions[0].type.value == "reply"
    assert "general" in plan.actions[0].params["message"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_agent.py::test_generate_plan_with_guild_context -v
```
Expected: FAIL — `TypeError: generate_plan() got an unexpected keyword argument 'guild_context'`

- [ ] **Step 3: Update agent.py**

Replace `src/architect/agent/agent.py` with:

```python
import json

from ..config import settings
from ..models.actions import ActionType
from ..models.plan import Plan
from .providers.base import LLMProvider
from .providers.claude import ClaudeProvider
from .providers.openai import OpenAIProvider

# Derived from enum — automatically stays in sync when new ActionTypes are added.
_VALID_TYPES = ", ".join(f'"{t.value}"' for t in ActionType)

# Concrete example: one instance per ActionType. The LLM copies structure, not schema metadata.
_PLAN_EXAMPLE = json.dumps(
    {
        "title": "Example Server",
        "description": "Brief description of what this plan creates.",
        "actions": [
            {"type": "create_category", "params": {"name": "General"}},
            {"type": "create_text_channel", "params": {"name": "welcome", "category": "General"}},
            {"type": "create_voice_channel", "params": {"name": "Lounge", "category": "General"}},
            {"type": "create_role", "params": {"name": "Member", "color": "#3498DB", "mentionable": True}},
            {
                "type": "set_channel_permissions",
                "params": {
                    "channel": "welcome",
                    "role": "Member",
                    "allow": ["read_messages"],
                    "deny": ["send_messages"],
                },
            },
            {"type": "reply", "params": {"message": "Here are the current channels: #general, #welcome"}},
        ],
    },
    indent=2,
)

SYSTEM_PROMPT = (
    "You are a Discord server architect.\n\n"
    "Reply ONLY with a JSON object that has exactly these three keys:\n"
    '  "title"       — a short string name for the plan\n'
    '  "description" — a one-sentence summary\n'
    '  "actions"     — an array of action objects\n\n'
    "Each action object must have exactly two keys:\n"
    f'  "type"   — one of: {_VALID_TYPES}\n'
    '  "params" — an object whose keys depend on the action type\n\n'
    'For read-only requests (listing channels, roles, etc.), use the "reply" action type with '
    'params: {"message": "..."}. Use the server state provided in the user message to populate '
    "the reply.\n\n"
    f"Example (follow this structure exactly, no extra keys, no markdown):\n{_PLAN_EXAMPLE}\n\n"
    "Reply ONLY with valid JSON. No markdown fences. No explanation. No schema keys."
)


def _build_provider() -> LLMProvider:
    if settings.llm_provider == "claude":
        return ClaudeProvider(settings.llm_api_key, settings.llm_model)
    if settings.llm_provider == "openai":
        return OpenAIProvider(settings.llm_api_key, settings.llm_model)
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider!r}")


class ArchitectAgent:
    def __init__(self) -> None:
        self._provider = _build_provider()

    async def generate_plan(self, prompt: str, guild_context: str = "") -> Plan:
        user_prompt = prompt
        if guild_context:
            user_prompt = f"{prompt}\n\nCurrent server state:\n{guild_context}"
        raw = await self._provider.complete(SYSTEM_PROMPT, user_prompt)
        return Plan.model_validate_json(raw)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_agent.py -v
```
Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/architect/agent/agent.py tests/test_agent.py
git commit -m "feat(agent): add reply action example, guild_context param"
```

---

### Task 4: Pass guild state from bot command to agent

**Files:**
- Modify: `src/architect/bot/commands.py`

- [ ] **Step 1: Add `_serialize_guild` and wire it up**

Replace `src/architect/bot/commands.py` with:

```python
import discord
from discord import app_commands
from discord.ext import commands

from ..agent.agent import ArchitectAgent
from ..executor.executor import Executor
from .views import ConfirmView, build_plan_embed


def _serialize_guild(guild: discord.Guild | None) -> str:
    if guild is None:
        return ""
    categories = [cat.name for cat in guild.categories]
    text_channels = [f"#{ch.name}" for ch in guild.text_channels]
    voice_channels = [ch.name for ch in guild.voice_channels]
    roles = [r.name for r in guild.roles if r.name != "@everyone"]
    parts = [
        f"Categories: {', '.join(categories) or 'none'}",
        f"Text channels: {', '.join(text_channels) or 'none'}",
        f"Voice channels: {', '.join(voice_channels) or 'none'}",
        f"Roles: {', '.join(roles) or 'none'}",
    ]
    return "\n".join(parts)


class ArchitectCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.agent = ArchitectAgent()
        self.executor = Executor()

    @app_commands.command(
        name="architect",
        description="Generate and execute a Discord configuration plan.",
    )
    @app_commands.describe(prompt="Describe the channels, categories and roles to create")
    @app_commands.default_permissions(administrator=True)
    async def architect(self, interaction: discord.Interaction, prompt: str) -> None:
        await interaction.response.defer(ephemeral=True)

        guild_context = _serialize_guild(interaction.guild)

        try:
            plan = await self.agent.generate_plan(prompt, guild_context=guild_context)
        except Exception as e:
            await interaction.followup.send(
                f"Error generating plan: {e}", ephemeral=True
            )
            return

        embed = build_plan_embed(plan)
        view = ConfirmView(plan, invoker_id=interaction.user.id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        await view.wait()

        if not view.confirmed:
            return

        if interaction.guild is None:
            await interaction.followup.send(
                "This command must be used inside a server.", ephemeral=True
            )
            return

        try:
            results = await self.executor.execute(plan, interaction.guild)
            summary = "\n".join(f"✅ {r}" for r in results)
            await interaction.followup.send(f"**Plan executed:**\n{summary}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(
                f"Error during execution: {e}", ephemeral=True
            )
```

- [ ] **Step 2: Run full test suite**

```bash
uv run pytest -v
```
Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add src/architect/bot/commands.py
git commit -m "feat(bot): serialize guild state and pass to agent as context"
```

---

## Verification

1. `uv run pytest` — all tests green
2. Restart the bot, type `/architect list all the channels and roles`
3. Expected: plan shows one `reply` action whose message lists actual server channels and roles
4. Confirm — "Plan executed: ✅ \<the list\>"
5. Type `/architect create a category called Test` — confirm mutation still works normally
