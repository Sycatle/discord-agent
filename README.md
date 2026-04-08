# ai-discord-architect

A Discord bot that turns an admin prompt into a structured plan for configuring your server — then executes it after mandatory human confirmation.

```
/architect "Create 3 gaming channels with Joueur and Modérateur roles"
```

The bot generates a preview embed, waits for confirmation, then executes. No mutation happens without an explicit approval.

## What it does

- **Generate** — sends your prompt to Claude or OpenAI, gets back a validated JSON plan
- **Preview** — shows a Discord embed listing every action before anything runs
- **Confirm** — you click ✅ or ❌ (120s timeout, bound to the invoking admin)
- **Execute** — creates categories, channels, roles, and permissions atomically

## Supported actions

| Action | Description |
|---|---|
| `create_category` | Create a channel category |
| `create_text_channel` | Create a text channel, optionally in a category |
| `create_voice_channel` | Create a voice channel, optionally in a category |
| `create_role` | Create a role with color and mentionable flag |
| `set_channel_permissions` | Set role-level overwrites on a channel |

## Stack

Python 3.12 · uv · discord.py 2.x · Pydantic v2 · Anthropic / OpenAI SDKs

## Quick start

See [SETUP.md](SETUP.md) for the full Discord application setup and configuration guide.

```bash
uv sync
cp .env.example .env
# fill in .env
uv run architect
```

## License

MIT
