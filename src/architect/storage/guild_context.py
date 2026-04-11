from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"


class GuildContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guild_id: int
    name: str = ""
    objectives: str = ""
    tone: str = ""
    rules: str = ""


def load(guild_id: int) -> GuildContext | None:
    path = DATA_DIR / f"{guild_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return GuildContext.model_validate(data)
    except Exception as exc:
        logger.warning("Failed to load guild context for %d: %s", guild_id, exc)
        return None


def save(ctx: GuildContext) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{ctx.guild_id}.json"
    path.write_text(ctx.model_dump_json(indent=2), encoding="utf-8")
