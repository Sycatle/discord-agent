from __future__ import annotations

import json
import logging
import logging.handlers
from pathlib import Path
from typing import Any

# Champs structurés autorisés via `extra={...}` — on les recopie tels quels
# dans le JSON pour pouvoir filtrer/grepper en prod sans regex sur le message.
_STRUCTURED_FIELDS = (
    "event",
    "tool_name",
    "guild_id",
    "channel_id",
    "user_id",
    "action_count",
    "success",
    "rolled_back",
    "errors",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        for key in _STRUCTURED_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                data[key] = value
        return json.dumps(data, default=str, ensure_ascii=False)


def setup_jsonl_handler(data_dir: Path) -> None:
    """Attach a 10MB rotating JSONL handler to the root logger.

    Idempotent : s'il existe déjà un handler vers le même fichier on ne le
    duplique pas (évite les doublons en cas de reload en dev).
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "architect.jsonl"
    root = logging.getLogger()
    for h in root.handlers:
        if (
            isinstance(h, logging.handlers.RotatingFileHandler)
            and Path(h.baseFilename) == log_path.resolve()
        ):
            return
    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(JsonFormatter())
    handler.setLevel(logging.INFO)
    root.addHandler(handler)
