import os

os.environ.setdefault("DISCORD_TOKEN", "fake_discord_token")
os.environ.setdefault("DISCORD_GUILD_IDS", "123456789")
os.environ.setdefault("LLM_PROVIDER", "claude")
os.environ.setdefault("LLM_API_KEY", "fake_api_key")
os.environ.setdefault("LLM_MODEL", "")

import pytest


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    """Redirect `settings.data_dir` to a per-test tmp dir + open the
    guild whitelist for the values tests use.

    Without the data_dir redirect, anything that uses the default `data/`
    (history, snapshots, guild context JSON) leaks state between tests
    AND with the developer's working directory.

    The whitelist patch enumerates every guild id used in the test suite
    EXCEPT `999999999`, which test_bot_events.py uses precisely to
    exercise the "guild not configured" refusal path.
    """
    from architect.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(
        settings,
        "discord_guild_ids",
        [1, 42, 99, 123, 4242, 4243, 123456789],
    )
