# ai-discord-architect MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Discord bot that transforms an admin prompt into a validated action plan, previews it, and executes it on confirmation.

**Architecture:** Layered — `models/` (Pydantic schemas + whitelist) → `agent/` (LLM provider abstraction) → `executor/` (Discord API calls) → `bot/` (slash command + UI). Each layer only imports the layer below it.

**Tech Stack:** Python 3.12, uv, discord.py 2.x, Pydantic v2, pydantic-settings, anthropic SDK, openai SDK, pytest, pytest-asyncio

---

## File Map

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | uv project, deps, entry point, pytest config |
| `CLAUDE.md` | Project rules for AI agents |
| `.env.example` | Documented env var template |
| `src/architect/__init__.py` | Package marker |
| `src/architect/config.py` | Pydantic Settings — single source of env vars |
| `src/architect/models/__init__.py` | Package marker |
| `src/architect/models/actions.py` | `ActionType` enum (whitelist) + `Action` model |
| `src/architect/models/plan.py` | `Plan` model — `extra="forbid"` |
| `src/architect/agent/__init__.py` | Package marker |
| `src/architect/agent/providers/__init__.py` | Package marker |
| `src/architect/agent/providers/base.py` | `LLMProvider` ABC |
| `src/architect/agent/providers/claude.py` | Anthropic implementation |
| `src/architect/agent/providers/openai.py` | OpenAI implementation |
| `src/architect/agent/agent.py` | `ArchitectAgent` — prompt → `Plan` |
| `src/architect/executor/__init__.py` | Package marker |
| `src/architect/executor/executor.py` | `Executor` — `Plan` + `Guild` → results |
| `src/architect/bot/__init__.py` | Package marker |
| `src/architect/bot/views.py` | `ConfirmView` (buttons) + `build_plan_embed` |
| `src/architect/bot/commands.py` | `/architect` slash command cog |
| `src/architect/bot/bot.py` | `ArchitectBot` — setup, cog registration, sync |
| `src/architect/main.py` | Entry point |
| `tests/conftest.py` | Env vars for tests (module-level, before imports) |
| `tests/test_models.py` | Unit tests for `ActionType`, `Action`, `Plan` |
| `tests/test_agent.py` | Unit tests for `ArchitectAgent` with `MockProvider` |
| `tests/test_executor.py` | Unit tests for `Executor` with mocked `discord.Guild` |

---

## Task 1: Project Bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `CLAUDE.md`
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: git init**

```bash
cd /home/sycatle/Workspace/ai-discord-architect
git init
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "ai-discord-architect"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "discord.py>=2.4",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "anthropic>=0.28",
    "openai>=1.30",
]

[project.scripts]
architect = "architect.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/architect"]

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: Create `.env.example`**

```env
DISCORD_TOKEN=your_discord_bot_token
DISCORD_GUILD_ID=123456789
LLM_PROVIDER=claude
LLM_API_KEY=your_api_key
LLM_MODEL=
```

- [ ] **Step 4: Create `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
.venv/
.env
*.egg-info/
dist/
.pytest_cache/
```

- [ ] **Step 5: Create `CLAUDE.md`**

```markdown
# ai-discord-architect — CLAUDE.md

## Règles absolues

- **Jamais de mutation Discord sans confirmation humaine explicite.** Preview obligatoire avant tout.
- **JSON strict uniquement.** `Plan.model_config = ConfigDict(extra="forbid")` — ne jamais relâcher.
- **Whitelist via `ActionType` enum.** Toute nouvelle action passe par l'enum, pas de cas spéciaux.
- **Pas de mode admin libre.** Le bot exécute des plans validés, rien d'autre.

## Stack

Python 3.12 · uv · discord.py 2.x · Pydantic v2 · anthropic + openai SDKs

## Architecture

Layered : `models/` → `agent/` → `executor/` → `bot/`
Chaque couche ne connaît que la couche en dessous. `bot/` ne touche pas à `executor/` directement.

## Conventions

- Pas de DB pour le MVP — stateless.
- Config via Pydantic Settings (`config.py`), env vars, jamais hardcodé.
- Provider LLM sélectionnable via `LLM_PROVIDER=claude|openai` — pas de couplage fort.
- Tests avec mock LLM (`MockProvider`) et mock guild (`AsyncMock`).

## Ce qu'on ne fait PAS

- Pas de `DELETE_*` actions dans le MVP.
- Pas de logging persistant.
- Pas de retry automatique sur erreur LLM — on remonte l'erreur à l'admin.
- Pas de feature flag ou config dynamique — change le code, bump la version.
```

- [ ] **Step 6: Install dependencies**

```bash
uv sync --group dev
```

Expected: `.venv/` created, all packages installed without errors.

- [ ] **Step 7: Create package skeleton (all `__init__.py`)**

```bash
mkdir -p src/architect/models src/architect/agent/providers src/architect/executor src/architect/bot tests
touch src/architect/__init__.py
touch src/architect/models/__init__.py
touch src/architect/agent/__init__.py
touch src/architect/agent/providers/__init__.py
touch src/architect/executor/__init__.py
touch src/architect/bot/__init__.py
touch tests/__init__.py
```

- [ ] **Step 8: Commit**

```bash
git add .
git commit -m "chore: bootstrap project structure"
```

---

## Task 2: Models

**Files:**
- Create: `src/architect/models/actions.py`
- Create: `src/architect/models/plan.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_models.py
import pytest
from pydantic import ValidationError
from architect.models.actions import Action, ActionType
from architect.models.plan import Plan


def test_action_type_whitelist_rejects_unknown():
    with pytest.raises(ValidationError):
        Action(type="delete_channel", params={})


def test_action_type_accepts_all_valid():
    for t in ActionType:
        a = Action(type=t, params={"name": "test"})
        assert a.type == t


def test_plan_rejects_extra_fields():
    with pytest.raises(ValidationError):
        Plan(
            title="T",
            description="D",
            actions=[],
            unexpected_field="oops",
        )


def test_plan_valid_roundtrip():
    raw = '{"title":"T","description":"D","actions":[{"type":"create_category","params":{"name":"Gaming"}}]}'
    plan = Plan.model_validate_json(raw)
    assert plan.title == "T"
    assert plan.actions[0].type == ActionType.CREATE_CATEGORY
    assert plan.actions[0].params == {"name": "Gaming"}


def test_plan_rejects_unknown_action_type_in_json():
    raw = '{"title":"T","description":"D","actions":[{"type":"nuke_server","params":{}}]}'
    with pytest.raises(ValidationError):
        Plan.model_validate_json(raw)
```

- [ ] **Step 2: Run tests — expect failure**

```bash
uv run pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError` — `architect.models.actions` not found yet.

- [ ] **Step 3: Create `src/architect/models/actions.py`**

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


class Action(BaseModel):
    type: ActionType
    params: dict[str, Any]
```

- [ ] **Step 4: Create `src/architect/models/plan.py`**

```python
from pydantic import BaseModel, ConfigDict
from .actions import Action


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    actions: list[Action]
```

- [ ] **Step 5: Run tests — expect pass**

```bash
uv run pytest tests/test_models.py -v
```

Expected: 5 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/architect/models/ tests/test_models.py
git commit -m "feat: add Plan and Action models with ActionType whitelist"
```

---

## Task 3: Config

**Files:**
- Create: `src/architect/config.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `tests/conftest.py`**

This must set env vars at module level — before any test imports trigger `Settings()` instantiation.

```python
# tests/conftest.py
import os

os.environ.setdefault("DISCORD_TOKEN", "fake_discord_token")
os.environ.setdefault("DISCORD_GUILD_ID", "123456789")
os.environ.setdefault("LLM_PROVIDER", "claude")
os.environ.setdefault("LLM_API_KEY", "fake_api_key")
os.environ.setdefault("LLM_MODEL", "")
```

- [ ] **Step 2: Create `src/architect/config.py`**

```python
from typing import Literal
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    discord_token: str
    discord_guild_id: int
    llm_provider: Literal["claude", "openai"] = "claude"
    llm_api_key: str
    llm_model: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

- [ ] **Step 3: Verify config loads in test context**

```bash
uv run pytest tests/ -v --co -q
```

Expected: test collection succeeds without `ValidationError` from `Settings()`.

- [ ] **Step 4: Commit**

```bash
git add src/architect/config.py tests/conftest.py
git commit -m "feat: add Pydantic Settings config and test env setup"
```

---

## Task 4: LLM Providers

**Files:**
- Create: `src/architect/agent/providers/base.py`
- Create: `src/architect/agent/providers/claude.py`
- Create: `src/architect/agent/providers/openai.py`

No direct unit tests — providers are thin wrappers around SDK clients. Covered by `test_agent.py` via `MockProvider`.

- [ ] **Step 1: Create `src/architect/agent/providers/base.py`**

```python
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return raw JSON string. Pydantic validation is the caller's responsibility."""
```

- [ ] **Step 2: Create `src/architect/agent/providers/claude.py`**

```python
import anthropic
from .base import LLMProvider

DEFAULT_MODEL = "claude-sonnet-4-6"


class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "") -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model or DEFAULT_MODEL

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return msg.content[0].text
```

- [ ] **Step 3: Create `src/architect/agent/providers/openai.py`**

```python
from openai import AsyncOpenAI
from .base import LLMProvider

DEFAULT_MODEL = "gpt-4o"


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "") -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model or DEFAULT_MODEL

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        resp = await self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content
```

- [ ] **Step 4: Verify imports work**

```bash
uv run python -c "from architect.agent.providers.claude import ClaudeProvider; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/architect/agent/providers/
git commit -m "feat: add LLMProvider ABC with Claude and OpenAI implementations"
```

---

## Task 5: Agent

**Files:**
- Create: `src/architect/agent/agent.py`
- Create: `tests/test_agent.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_agent.py
import json
import pytest
from pydantic import ValidationError
from unittest.mock import patch

from architect.agent.providers.base import LLMProvider
from architect.models.plan import Plan


class MockProvider(LLMProvider):
    def __init__(self, response: str) -> None:
        self._response = response

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        return self._response


VALID_PLAN_JSON = json.dumps({
    "title": "Plan Gaming",
    "description": "Crée un espace gaming",
    "actions": [
        {"type": "create_category", "params": {"name": "Gaming"}},
        {"type": "create_text_channel", "params": {"name": "general", "category": "Gaming"}},
    ],
})

INVALID_JSON = "not json at all"

INVALID_ACTION_JSON = json.dumps({
    "title": "T",
    "description": "D",
    "actions": [{"type": "nuke_server", "params": {}}],
})


async def test_generate_plan_valid():
    from architect.agent.agent import ArchitectAgent
    with patch("architect.agent.agent._build_provider", return_value=MockProvider(VALID_PLAN_JSON)):
        agent = ArchitectAgent()
    plan = await agent.generate_plan("Crée un espace gaming")
    assert isinstance(plan, Plan)
    assert plan.title == "Plan Gaming"
    assert len(plan.actions) == 2


async def test_generate_plan_invalid_json_raises():
    from architect.agent.agent import ArchitectAgent
    with patch("architect.agent.agent._build_provider", return_value=MockProvider(INVALID_JSON)):
        agent = ArchitectAgent()
    with pytest.raises(Exception):
        await agent.generate_plan("prompt")


async def test_generate_plan_unknown_action_raises():
    from architect.agent.agent import ArchitectAgent
    with patch("architect.agent.agent._build_provider", return_value=MockProvider(INVALID_ACTION_JSON)):
        agent = ArchitectAgent()
    with pytest.raises(ValidationError):
        await agent.generate_plan("prompt")
```

- [ ] **Step 2: Run tests — expect failure**

```bash
uv run pytest tests/test_agent.py -v
```

Expected: `ModuleNotFoundError` — `architect.agent.agent` not found yet.

- [ ] **Step 3: Create `src/architect/agent/agent.py`**

```python
import json

from ..config import settings
from ..models.plan import Plan
from .providers.base import LLMProvider
from .providers.claude import ClaudeProvider
from .providers.openai import OpenAIProvider

SYSTEM_PROMPT_TEMPLATE = """\
Tu es un architecte de serveur Discord. Génère un plan structuré en JSON strict \
selon ce schéma exactement :
{schema}
Réponds UNIQUEMENT avec le JSON valide, sans balises markdown, sans explication."""


def _build_provider() -> LLMProvider:
    if settings.llm_provider == "claude":
        return ClaudeProvider(settings.llm_api_key, settings.llm_model)
    return OpenAIProvider(settings.llm_api_key, settings.llm_model)


class ArchitectAgent:
    def __init__(self) -> None:
        self._provider = _build_provider()
        self._schema = json.dumps(Plan.model_json_schema(), indent=2)

    async def generate_plan(self, prompt: str) -> Plan:
        system = SYSTEM_PROMPT_TEMPLATE.format(schema=self._schema)
        raw = await self._provider.complete(system, prompt)
        return Plan.model_validate_json(raw)
```

- [ ] **Step 4: Run tests — expect pass**

```bash
uv run pytest tests/test_agent.py -v
```

Expected: 3 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/architect/agent/agent.py tests/test_agent.py
git commit -m "feat: add ArchitectAgent with LLM provider injection"
```

---

## Task 6: Executor

**Files:**
- Create: `src/architect/executor/executor.py`
- Create: `tests/test_executor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_executor.py
import pytest
from unittest.mock import AsyncMock, MagicMock
import discord

from architect.executor.executor import Executor
from architect.models.actions import Action, ActionType
from architect.models.plan import Plan


def _make_guild() -> MagicMock:
    """Build a minimal mock discord.Guild."""
    guild = MagicMock(spec=discord.Guild)
    guild.categories = []
    guild.roles = []
    guild.channels = []

    cat = MagicMock(); cat.name = "Gaming"
    ch_text = MagicMock(); ch_text.name = "general"
    ch_voice = MagicMock(); ch_voice.name = "Vocal"
    role = MagicMock(); role.name = "Joueur"

    guild.create_category = AsyncMock(return_value=cat)
    guild.create_text_channel = AsyncMock(return_value=ch_text)
    guild.create_voice_channel = AsyncMock(return_value=ch_voice)
    guild.create_role = AsyncMock(return_value=role)
    return guild


async def test_execute_create_category():
    guild = _make_guild()
    plan = Plan(
        title="T", description="D",
        actions=[Action(type=ActionType.CREATE_CATEGORY, params={"name": "Gaming"})]
    )
    results = await Executor().execute(plan, guild)
    assert len(results) == 1
    assert "Gaming" in results[0]
    guild.create_category.assert_called_once_with(name="Gaming")


async def test_execute_create_text_channel():
    guild = _make_guild()
    plan = Plan(
        title="T", description="D",
        actions=[Action(type=ActionType.CREATE_TEXT_CHANNEL, params={"name": "general"})]
    )
    results = await Executor().execute(plan, guild)
    assert "general" in results[0]
    guild.create_text_channel.assert_called_once_with(name="general", category=None)


async def test_execute_create_role():
    guild = _make_guild()
    plan = Plan(
        title="T", description="D",
        actions=[Action(type=ActionType.CREATE_ROLE, params={"name": "Joueur"})]
    )
    results = await Executor().execute(plan, guild)
    assert "Joueur" in results[0]
    guild.create_role.assert_called_once()


async def test_execute_multiple_actions_in_order():
    guild = _make_guild()
    plan = Plan(
        title="T", description="D",
        actions=[
            Action(type=ActionType.CREATE_CATEGORY, params={"name": "Gaming"}),
            Action(type=ActionType.CREATE_TEXT_CHANNEL, params={"name": "general"}),
        ]
    )
    results = await Executor().execute(plan, guild)
    assert len(results) == 2
    guild.create_category.assert_called_once()
    guild.create_text_channel.assert_called_once()
```

- [ ] **Step 2: Run tests — expect failure**

```bash
uv run pytest tests/test_executor.py -v
```

Expected: `ModuleNotFoundError` — `architect.executor.executor` not found.

- [ ] **Step 3: Create `src/architect/executor/executor.py`**

```python
import discord

from ..models.actions import ActionType
from ..models.plan import Plan


class Executor:
    async def execute(self, plan: Plan, guild: discord.Guild) -> list[str]:
        results = []
        for action in plan.actions:
            result = await self._dispatch(action, guild)
            results.append(result)
        return results

    async def _dispatch(self, action, guild: discord.Guild) -> str:
        p = action.params
        match action.type:
            case ActionType.CREATE_CATEGORY:
                cat = await guild.create_category(name=p["name"])
                return f"Catégorie créée : {cat.name}"

            case ActionType.CREATE_TEXT_CHANNEL:
                category = discord.utils.get(guild.categories, name=p.get("category"))
                ch = await guild.create_text_channel(name=p["name"], category=category)
                return f"Salon texte créé : #{ch.name}"

            case ActionType.CREATE_VOICE_CHANNEL:
                category = discord.utils.get(guild.categories, name=p.get("category"))
                ch = await guild.create_voice_channel(name=p["name"], category=category)
                return f"Salon vocal créé : {ch.name}"

            case ActionType.CREATE_ROLE:
                role = await guild.create_role(
                    name=p["name"],
                    color=discord.Color(int(p.get("color", "0x000000"), 16)),
                    mentionable=p.get("mentionable", False),
                )
                return f"Rôle créé : @{role.name}"

            case ActionType.SET_CHANNEL_PERMISSIONS:
                channel = discord.utils.get(guild.channels, name=p["channel"])
                role = discord.utils.get(guild.roles, name=p["role"])
                overwrite = discord.PermissionOverwrite(**p.get("permissions", {}))
                await channel.set_permissions(role, overwrite=overwrite)
                return f"Permissions définies : #{p['channel']} → @{p['role']}"
```

- [ ] **Step 4: Run tests — expect pass**

```bash
uv run pytest tests/test_executor.py -v
```

Expected: 4 tests PASSED.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest -v
```

Expected: all 12 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/architect/executor/executor.py tests/test_executor.py
git commit -m "feat: add Executor with handlers for all 5 whitelisted ActionTypes"
```

---

## Task 7: Bot Layer

**Files:**
- Create: `src/architect/bot/views.py`
- Create: `src/architect/bot/commands.py`
- Create: `src/architect/bot/bot.py`
- Create: `src/architect/main.py`

The Discord bot layer is not unit-tested (requires a live gateway connection). Correctness is verified by the end-to-end test described in the spec.

- [ ] **Step 1: Create `src/architect/bot/views.py`**

```python
import discord

from ..models.plan import Plan


class ConfirmView(discord.ui.View):
    def __init__(self, plan: Plan, invoker_id: int) -> None:
        super().__init__(timeout=120)
        self.plan = plan
        self.invoker_id = invoker_id
        self.confirmed = False

    def _is_invoker(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.invoker_id

    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message(
                "Seul l'admin qui a lancé la commande peut confirmer.", ephemeral=True
            )
            return
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_invoker(interaction):
            await interaction.response.send_message(
                "Seul l'admin qui a lancé la commande peut annuler.", ephemeral=True
            )
            return
        self.stop()
        await interaction.response.send_message("Plan annulé.", ephemeral=True)


def build_plan_embed(plan: Plan) -> discord.Embed:
    embed = discord.Embed(
        title=f"Plan : {plan.title}",
        description=plan.description,
        color=discord.Color.blurple(),
    )
    actions_text = "\n".join(
        f"`{i + 1}.` **{a.type}** — {a.params}"
        for i, a in enumerate(plan.actions)
    )
    embed.add_field(name=f"{len(plan.actions)} action(s)", value=actions_text, inline=False)
    embed.set_footer(text="Confirmez ou annulez dans 120s.")
    return embed
```

- [ ] **Step 2: Create `src/architect/bot/commands.py`**

```python
import discord
from discord import app_commands
from discord.ext import commands

from ..agent.agent import ArchitectAgent
from ..executor.executor import Executor
from .views import ConfirmView, build_plan_embed


class ArchitectCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.agent = ArchitectAgent()
        self.executor = Executor()

    @app_commands.command(
        name="architect",
        description="Génère et exécute un plan de configuration Discord.",
    )
    @app_commands.describe(prompt="Décris les salons, catégories et rôles à créer")
    @app_commands.default_permissions(administrator=True)
    async def architect(self, interaction: discord.Interaction, prompt: str) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            plan = await self.agent.generate_plan(prompt)
        except Exception as e:
            await interaction.followup.send(
                f"Erreur lors de la génération du plan : {e}", ephemeral=True
            )
            return

        embed = build_plan_embed(plan)
        view = ConfirmView(plan, invoker_id=interaction.user.id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        await view.wait()

        if not view.confirmed:
            return

        try:
            results = await self.executor.execute(plan, interaction.guild)
            summary = "\n".join(f"✅ {r}" for r in results)
            await interaction.followup.send(f"**Plan exécuté :**\n{summary}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(
                f"Erreur lors de l'exécution : {e}", ephemeral=True
            )
```

- [ ] **Step 3: Create `src/architect/bot/bot.py`**

```python
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
```

- [ ] **Step 4: Create `src/architect/main.py`**

```python
import asyncio

from .bot.bot import ArchitectBot
from .config import settings


def main() -> None:
    bot = ArchitectBot()
    asyncio.run(bot.start(settings.discord_token))


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Verify import chain is clean**

```bash
uv run python -c "from architect.bot.bot import ArchitectBot; print('OK')"
```

Expected: `OK` (no import errors).

- [ ] **Step 6: Run full test suite one last time**

```bash
uv run pytest -v
```

Expected: 12 tests PASSED, 0 failures.

- [ ] **Step 7: Commit**

```bash
git add src/architect/bot/ src/architect/main.py
git commit -m "feat: add bot layer — slash command, confirm view, entrypoint"
```

---

## End-to-End Verification Checklist

Before considering the MVP complete, verify in a real Discord server:

1. `uv run architect` → terminal shows `Bot connecté : <BotName>#XXXX`
2. `/architect "Crée un salon #général dans une catégorie Communauté"` → ephemeral embed appears with 2 actions
3. Click ✅ Confirmer → category + text channel appear in the server
4. Repeat, then do NOT click for 120s → buttons become disabled automatically
5. Have a second user try to click Confirmer → they see "Seul l'admin..."
6. Set `LLM_API_KEY=invalid` and retry → clean error message, no crash, no partial execution
