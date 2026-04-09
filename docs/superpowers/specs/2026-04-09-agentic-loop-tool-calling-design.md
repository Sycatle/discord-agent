# Agentic Loop with Native Tool Calling

**Date:** 2026-04-09  
**Status:** Implemented

## Context

The bot previously exposed a single `/architect` slash command. Every request triggered a full JSON Plan generation, showed a global Confirm/Cancel embed, and executed all actions at once. There was no intent routing (plan vs reply vs clarify), no multi-turn conversation, and actions were Pydantic models rather than native LLM tools.

## Goals

- Remove `/architect`, replace with natural interaction via mention or reply
- LLM decides what to do via native tool calling (Anthropic/OpenAI function calling)
- Each Discord mutation requires explicit per-step confirmation
- In-memory conversation history per channel (multi-turn)
- Intent routing emerges naturally from tool use: no tool calls = reply; `ask_clarification` = question; mutation tools = plan + confirm

## Architecture

```
User (@bot or reply)
  → bot/events.py (on_message)
      → agent/agent.py (step)            # one LLM call per step
          → agent/providers/claude.py    # or openai.py
          ← list[AgentEvent]
      → executor/executor.py (execute)   # per tool call
          → discord.Guild API
      → bot/views.py (ConfirmView)       # per mutation tool
      → bot/history.py (ConversationHistory)
```

### Layers

```
models/    → agent/    → executor/    → bot/
```

Each layer only knows the layer below it.

## Key Design Decisions

### Tool Calling as Intent Router

The LLM receives 8 tools and decides which to call:

| Tool | Category | Confirmation |
|------|----------|-------------|
| `create_category` | mutation | required |
| `create_text_channel` | mutation | required |
| `create_voice_channel` | mutation | required |
| `create_role` | mutation | required |
| `set_channel_permissions` | mutation | required |
| `list_channels` | read-only | none |
| `list_roles` | read-only | none |
| `ask_clarification` | meta | none |

If the LLM returns only text (no tool calls) → conversational reply.

### Agent Step Loop

`ArchitectAgent.step()` makes exactly **one LLM call** and returns `list[AgentEvent]`. The multi-turn loop lives in `bot/events.py`:

```
while steps < MAX_STEPS (10):
    events = await agent.step(history, guild_context)
    for event in events:
        ReplyEvent         → send text, stop loop
        ClarificationEvent → send question, stop loop
        ReadOnlyToolEvent  → execute immediately, add result to history
        ConfirmationRequiredEvent → show ConfirmView, wait for user
            CONFIRMED    → execute, add result
            CANCELLED    → add "cancelled" to history, LLM adapts
            CANCELLED_ALL → add "cancelled" to history, stop loop
    if no tool calls in this step → stop
```

### Anthropic Message Format

History is stored in Anthropic's native format. Tool results follow the required order:
1. `{"role": "assistant", "content": [tool_use blocks]}`
2. `{"role": "user", "content": [tool_result blocks]}`

The OpenAI provider converts to/from Anthropic format internally.

### ConfirmView

Three buttons (Confirm ✅, Cancel ❌, Cancel All 🛑) with an `asyncio.Future` for async result signaling. Future is lazy-initialized on first async call to avoid issues outside the running event loop.

## File Structure

```
src/architect/
├── models/
│   └── actions.py          # ActionType enum (5 mutation types, no REPLY)
├── agent/
│   ├── agent.py            # ArchitectAgent.step()
│   ├── tools.py            # get_tools(), READONLY_TOOLS, META_TOOLS
│   ├── events.py           # AgentEvent dataclasses
│   └── providers/
│       ├── base.py         # LLMProvider.call_with_tools()
│       ├── claude.py
│       └── openai.py
├── executor/
│   └── executor.py         # execute(tool_name, params, guild) -> str
└── bot/
    ├── bot.py              # ArchitectBot + setup_hook
    ├── events.py           # BotEvents cog, _run_agent_loop
    ├── history.py          # ConversationHistory (in-memory)
    └── views.py            # ConfirmView, ConfirmResult

tests/
├── test_models.py
├── test_tools.py
├── test_events.py
├── test_agent.py
├── test_executor.py
├── test_history.py
├── test_views.py
└── test_bot_events.py
```

## Verification

1. `uv run python -m architect` — bot starts
2. `@bot liste les channels` → read-only tool, immediate reply
3. `@bot crée une catégorie "test"` → 🔧 confirmation prompt
4. `@bot arrange les channels` → ask_clarification question
5. Reply to clarification (no @mention needed) → bot continues the conversation
6. `uv run pytest` → 59 tests pass
