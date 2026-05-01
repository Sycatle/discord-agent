# Contributing

Thanks for your interest in contributing! This document covers the
local dev setup, the conventions enforced by CI, and the recipe for
adding a new Discord action.

## Dev setup

```bash
git clone https://github.com/sycatle/ai-discord-architect
cd ai-discord-architect
uv sync --all-groups
pre-commit install
```

`pre-commit install` registers the formatter, linter and type-checker
to run automatically on `git commit`.

## Run the checks

```bash
uv run ruff check          # lint
uv run ruff format         # format
uv run mypy src/architect  # static types (strict)
uv run pytest              # tests + branch coverage (gate at 90%)
```

CI runs all four on every push and pull request to `main`. PRs that
don't pass CI won't be merged.

## Conventions

- **Conventional Commits.** Prefix commits with `feat:`, `fix:`,
  `refactor:`, `chore:`, `docs:`, `test:`, etc. The history is the
  changelog.
- **One concern per PR.** Refactor and feature in separate commits if
  not separate PRs.
- **English everywhere.** Code, comments, docstrings, error messages,
  commit messages — all English. Keeps the project portable.
- **No silent fallbacks.** If a Discord call fails, surface the error
  to the user and the structured log. Don't retry, don't swallow.
- **Coverage ≥ 90%.** Every new handler needs a test. The fail_under
  gate in `pyproject.toml` enforces it.

## Adding a new `ActionType`

See [ARCHITECTURE.md](ARCHITECTURE.md#adding-a-new-actiontype) for the
five-step recipe (enum → params model → handler → register → test).
The summary:

1. Add to `ActionType` in `src/architect/models/actions.py`.
2. Add a Pydantic params model in `src/architect/models/params/<domain>.py`.
3. Write the async handler in `src/architect/executor/handlers/<domain>.py`.
4. Register in `executor/handlers/__init__.py` (and `permissions.py`
   for mutations, plus `rollback.py` if the action is invertible).
5. Test in `tests/handlers/<domain>.py` and `tests/models/test_params.py`.

`tools.py` will pick up the schema automatically — no code change
needed there.

## Capturing demo media

The README references `docs/assets/demo.gif`. To regenerate it:

1. Run the bot against a test guild.
2. Record the terminal + Discord side-by-side using
   [asciinema](https://asciinema.org/) (terminal) or
   [OBS Studio](https://obsproject.com/) (full window).
3. Convert to a small GIF (`ffmpeg -i recording.mp4 -vf fps=10 demo.gif`).
4. Drop the file into `docs/assets/demo.gif`. Keep it under 2 MB so
   the README loads quickly on slow connections.

## Reporting issues

Please open issues on GitHub with:

- The command you ran (or the prompt you sent the agent).
- The full embed / log output (including the JSONL log line if
  available).
- Your Python and discord.py versions.
- Whether the bot has the listed permissions in your guild.

## Code of conduct

Be respectful. Critique code, not people. PRs and issues that violate
this will be closed without comment.
