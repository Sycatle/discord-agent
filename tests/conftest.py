import os

os.environ.setdefault("DISCORD_TOKEN", "fake_discord_token")
os.environ.setdefault("DISCORD_GUILD_ID", "123456789")
os.environ.setdefault("LLM_PROVIDER", "claude")
os.environ.setdefault("LLM_API_KEY", "fake_api_key")
os.environ.setdefault("LLM_MODEL", "")

import pytest


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    """Redirect `settings.data_dir` to a per-test tmp dir.

    Without this, anything that uses the default `data/` (history,
    snapshots, guild context JSON) leaks state between tests AND with the
    developer's working directory. Cheap belt-and-braces.
    """
    from architect.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
