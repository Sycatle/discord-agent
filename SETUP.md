# Setup Guide

## 1. Create a Discord application

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application**, give it a name (e.g. `architect`)
3. Go to **Bot** → click **Add Bot**
4. Under **Token**, click **Reset Token** and copy it — this is your `DISCORD_TOKEN`
5. Disable **Public Bot** if you only want this on your own servers

## 2. Bot permissions and intents

In the **Bot** tab, enable the following **Privileged Gateway Intents**:

- **Message Content Intent** (so the bot can read mentions of itself)
- **Server Members Intent** (to resolve member targets)

For full functionality across the 27 supported actions, the bot needs these
guild permissions:

| Permission | Used by |
|---|---|
| Manage Channels | text/voice/forum/stage create / edit / delete, invites, set permissions |
| Manage Roles | role create / edit / delete / assign / remove |
| Manage Webhooks | webhook create / edit / delete |
| Manage Server | server settings, AutoMod rules, welcome screen |
| Manage Events | scheduled events |
| Moderate Members | member nickname / mute / deafen / timeout |
| Create Instant Invite | invite create |

You can request a narrower subset if you only need a subset of features —
the bot pre-checks each action's permission before calling Discord and
will reply with a clear "Missing permission" message if it lacks the
right.

## 3. Generate the invite URL

Go to **OAuth2 → URL Generator**:

- Scopes: `bot`, `applications.commands`
- Bot permissions: pick the ones from the table above

Copy the generated URL, open it in your browser, and invite the bot to
your server.

## 4. Get your Guild ID

In Discord, enable **Developer Mode** (Settings → Advanced → Developer Mode).
Right-click your server name → **Copy Server ID** — this is your
`DISCORD_GUILD_ID`.

## 5. Get an LLM API key

**Claude (default)**

Go to [console.anthropic.com](https://console.anthropic.com), create an
API key. Set `LLM_PROVIDER=claude` and `LLM_API_KEY=sk-ant-...`

**OpenAI**

Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys),
create an API key. Set `LLM_PROVIDER=openai` and `LLM_API_KEY=sk-...`

## 6. Configure the environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
DISCORD_TOKEN=your_bot_token_here
DISCORD_GUILD_ID=your_server_id_here
LLM_PROVIDER=claude          # claude | openai
LLM_API_KEY=your_api_key_here
LLM_MODEL=                   # optional — leave empty for provider default
```

`LLM_MODEL` defaults:

- Claude: `claude-sonnet-4-6`
- OpenAI: `gpt-4o`

## 7. Install dependencies and run

```bash
# Install uv if you don't have it
curl -Ls https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Start the bot
uv run architect
```

You should see:

```
Bot connected: architect#1234 (guild_id=123456789)
```

## 8. Talk to the bot

Mention the bot in your server (admin only):

```
@architect Create a Gaming category with #general and #voice, and a Player role
```

The bot will reply with a plan embed listing every action it intends
to take. Click **Confirm all** to execute the whole plan, **Atomic
(rollback on error)** to roll back if any step fails, **Review** to
approve actions one by one, or **Cancel** to abort. Confirmation
times out after 5 minutes.
