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
Chaque couche ne connaît que la couche en dessous. `bot/` n'appelle pas l'API Discord directement — elle délègue à `executor/`. `bot/` peut importer `executor/` mais ne doit pas bypasser la validation `agent/`.

Périmètre : ~40 ActionTypes whitelistés couvrant channels (text/voice/forum/stage), threads (create/archive/lock/unarchive), roles, permission overrides granulaires, members, modération (ban/kick/unban/bulk-timeout), scheduled events, automod, emojis & stickers, server settings, welcome screen.

## Conventions

- Pas de DB — stateless.
- Config via Pydantic Settings (`config.py`), env vars, jamais hardcodé.
- Provider LLM sélectionnable via `LLM_PROVIDER=claude|openai` — pas de couplage fort.
- Tests avec mock LLM (`MockProvider`) et mock guild (`AsyncMock`).
- Erreurs Discord : log via `logger.exception`, message structuré à l'utilisateur, jamais de stacktrace brute dans l'embed.

## Mode apprentissage (opt-in)

- `/architect audit` poste dans le channel un message qui amorce l'agent en mode read-only : il enchaîne `list_*` / `get_*` / `simulate_action`, puis enregistre ses observations via `record_finding` (catégorie `health` / `risk` / `opportunity` + sévérité 1-5).
- **Aucune mutation pendant l'audit.** Le flow normal (PlanView → ConfirmView) reste obligatoire pour exécuter quoi que ce soit.
- Les `findings` et `learned_constraints` sont persistés dans `GuildContext` et réinjectés au system prompt à chaque tour suivant — ce qui permet à l'agent de tenir compte de ce qu'il a appris.
- Les `learned_constraints` sont aussi auto-alimentées par les erreurs Discord apprenables (50013, 50024, 30005, 30013, etc.) : le bot ne refait pas la même erreur deux fois.

## Ce qu'on ne fait PAS

- Pas de logging persistant.
- Pas de retry automatique sur erreur LLM — on remonte l'erreur à l'admin.
- Pas de feature flag ou config dynamique — change le code, bump la version.
- Pas d'auto-confirmation pour les actions destructrices : `delete_*` passent par la même `ConfirmView` que les autres mutations, mais l'utilisateur doit valider explicitement (le mode `Tout confirmer` reste un opt-in conscient).
