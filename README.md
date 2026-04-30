# ai-discord-architect

Bot Discord piloté par un agent IA. Tu décris ce que tu veux en langage naturel, le bot génère un plan structuré (JSON validé), te montre un aperçu, et n'exécute qu'après confirmation explicite.

```
/architect "Crée 3 channels gaming avec les rôles Joueur et Modérateur"
@bot ajoute un règlement automod qui bloque les liens raccourcis
```

## Comment ça marche

1. **Generate** — l'agent (Claude ou OpenAI) traduit ta demande en plan JSON typé via tool calling
2. **Preview** — un embed Discord liste chaque action avant exécution
3. **Confirm** — `Tout confirmer`, `Réviser` (action par action), ou `Annuler`
4. **Execute** — l'`Executor` applique les actions séquentiellement avec rapport d'erreurs

Aucune mutation Discord ne se produit sans approbation humaine.

## Domaines couverts

Le bot pilote la quasi-totalité de l'API Discord serveur (27 actions whitelisted via `ActionType` enum) :

- **Channels** — text, voice, forum, stage, catégories, edit, delete, permissions, invites, webhooks
- **Roles** — création, edit, delete, assignation/retrait sur les membres
- **Members** — edit (nickname, mute, deaf, timeout, déplacement vocal)
- **Scheduled events** — création, edit, delete (voice/stage/external)
- **AutoMod** — règles de modération automatique (création, edit, delete)
- **Server settings** — nom, icône, locale, mode community, welcome screen

L'agent peut aussi **lire** l'état du serveur (channels, rôles, membres, invites, webhooks, events, automod) avant de proposer un plan, et demander des clarifications si la demande est ambiguë.

## Stack

Python 3.12 · uv · discord.py 2.x · Pydantic v2 · Anthropic / OpenAI SDKs

## Architecture

```
models/   →  ActionType enum + Pydantic Action (whitelist stricte, extra="forbid")
agent/    →  LLM provider (Claude/OpenAI), tool schemas, agentic loop
executor/ →  Handlers Discord par ActionType (single source of truth)
bot/      →  discord.py cog, embeds de confirmation, history conversation
```

Chaque couche ne connaît que celle d'en dessous. `bot/` ne touche pas l'API Discord directement — elle délègue à `executor/`.

## Permissions Discord requises

Le bot doit avoir, au minimum :
- `Manage Channels`, `Manage Roles`, `Manage Webhooks`, `Manage Server`, `Manage Events`, `Moderate Members`
- Intents : `message_content`, `members`, `guilds`

L'invitation OAuth doit inclure le scope `bot` + `applications.commands`.

## Quick start

```bash
uv sync
cp .env.example .env
# remplir DISCORD_TOKEN, DISCORD_GUILD_ID, LLM_PROVIDER, LLM_API_KEY
uv run architect
```

Voir [SETUP.md](SETUP.md) pour le détail (création de l'app Discord, perms, intents).

## Tests

```bash
uv run pytest
```

137 tests couvrent les modèles, l'executor (mock guild), le provider LLM (MockProvider), les vues, et la boucle agentic.

## License

MIT
