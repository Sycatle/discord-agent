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
