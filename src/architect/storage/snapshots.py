"""Disk persistence of guild snapshots taken before plan execution.

Each call to ``save_pre_exec_snapshot`` writes a JSON file under
``settings.data_dir / "snapshots" / "{guild_id}_{unix_ts}.json"``. The file
captures:

- the wall-clock timestamp (UTC, ISO-8601);
- the title and actions of the plan that is about to run;
- a serialised ``GuildSnapshot`` (categories, channels, roles, automod).

Purpose: if the bot crashes mid-execution or the user wants to inspect
what the guild looked like before a destructive plan, the JSON file is
enough for a human to manually reconstitute the state.

Auto-restoration is intentionally out of scope: replaying a snapshot
blindly could overwrite legitimate changes made between the crash and
the recovery. The file is a forensic artefact, not a rollback button.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from architect.config import settings
from architect.models.snapshot import GuildSnapshot

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = settings.data_dir / "snapshots"
DEFAULT_KEEP_LAST = 5


def _snapshot_dir() -> Path:
    """Resolve the snapshot directory lazily so tests can monkeypatch
    ``settings.data_dir`` after import."""
    return settings.data_dir / "snapshots"


def save_pre_exec_snapshot(
    guild_id: int,
    snapshot: GuildSnapshot,
    plan_title: str,
    plan_actions: list[dict[str, Any]],
) -> Path:
    """Persist a snapshot to disk; returns the written path.

    The filename includes the guild_id and a unix timestamp so multiple
    snapshots can coexist for the same guild. The directory is created
    on first call.
    """
    target_dir = _snapshot_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    ts = int(now.timestamp())
    path = target_dir / f"{guild_id}_{ts}.json"
    payload = {
        "timestamp": now.isoformat(),
        "guild_id": guild_id,
        "plan_title": plan_title,
        "plan_actions": plan_actions,
        "snapshot": asdict(snapshot),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def list_snapshots(guild_id: int) -> list[Path]:
    """Sorted-newest-first list of snapshot paths for the given guild."""
    target_dir = _snapshot_dir()
    if not target_dir.exists():
        return []
    paths = sorted(
        target_dir.glob(f"{guild_id}_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return paths


def load_latest_snapshot(guild_id: int) -> tuple[Path, dict[str, Any]] | None:
    """Return (path, payload) for the most recent snapshot, or None."""
    paths = list_snapshots(guild_id)
    if not paths:
        return None
    try:
        payload = json.loads(paths[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("failed to load snapshot %s: %s", paths[0], exc)
        return None
    return paths[0], payload


def prune_old_snapshots(guild_id: int, keep_last: int = DEFAULT_KEEP_LAST) -> int:
    """Delete all but the ``keep_last`` most recent snapshots for the guild.

    Returns the number of files deleted. Best-effort: I/O errors are
    logged but do not propagate — pruning is housekeeping, not critical.
    """
    paths = list_snapshots(guild_id)
    to_delete = paths[keep_last:]
    deleted = 0
    for p in to_delete:
        try:
            p.unlink()
            deleted += 1
        except OSError as exc:
            logger.warning("failed to delete snapshot %s: %s", p, exc)
    return deleted
