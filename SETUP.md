# Setup Guide

## 1. Create a Discord application

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application**, give it a name (e.g. `architect`)
3. Go to **Bot** → click **Add Bot**
4. Under **Token**, click **Reset Token** and copy it — this is your `DISCORD_TOKEN`
5. Disable **Public Bot** if you only want this on your own servers

## 2. Set bot permissions

In the **Bot** tab, under **Privileged Gateway Intents**, no extra intents are needed.

When generating the invite link (step 4), the bot needs these permissions:

- Manage Channels
- Manage Roles

## 3. Enable slash commands

Go to **OAuth2 → URL Generator**:

- Scopes: `bot`, `applications.commands`
- Bot permissions: `Manage Channels`, `Manage Roles`

Copy the generated URL, open it in your browser, and invite the bot to your server.

## 4. Get your Guild ID

In Discord, enable **Developer Mode** (Settings → Advanced → Developer Mode).  
Right-click your server name → **Copy Server ID** — this is your `DISCORD_GUILD_ID`.

## 5. Get an LLM API key

**Claude (default)**

Go to [console.anthropic.com](https://console.anthropic.com), create an API key.  
Set `LLM_PROVIDER=claude` and `LLM_API_KEY=sk-ant-...`

**OpenAI**

Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys), create an API key.  
Set `LLM_PROVIDER=openai` and `LLM_API_KEY=sk-...`

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
# Install uv if needed
curl -Ls https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Start the bot
uv run architect
```

You should see:

```
Bot connecté : architect#1234 (guild_id=123456789)
```

## 8. Use the command

In your Discord server (admin only):

```
/architect <prompt>
```

Example:

```
/architect Create a Gaming category with #general and #voice, and a Joueur role
```

The bot will show a plan embed. Click **Confirmer** to execute or **Annuler** to abort.  
The confirmation times out after 120 seconds.
