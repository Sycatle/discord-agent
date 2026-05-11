from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from architect.config import settings

logger = logging.getLogger(__name__)

DATA_DIR = settings.data_dir

_PREFERENCES_CAP = 20
_FINDINGS_CAP = 20
_LEARNED_CONSTRAINTS_CAP = 30

FindingCategory = Literal["health", "risk", "opportunity"]


class Finding(BaseModel):
    """An audit-mode observation worth surfacing on subsequent turns."""

    model_config = ConfigDict(extra="forbid")

    category: FindingCategory
    summary: str
    severity: int = Field(ge=1, le=5)


class GuildContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guild_id: int
    name: str = ""
    objectives: str = ""
    tone: str = ""
    rules: str = ""
    preferences: list[str] = Field(default_factory=list)
    recent_decisions: list[str] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    learned_constraints: list[str] = Field(default_factory=list)

    def record(self, text: str, kind: str) -> bool:
        """Append a preference or decision. FIFO cap at 20.

        Returns False when the entry is a duplicate of the most recent one
        (avoids the agent spamming `record_preference` on every turn).
        """
        text = text.strip()
        if not text:
            return False
        bucket = self.preferences if kind == "preference" else self.recent_decisions
        if bucket and bucket[-1] == text:
            return False
        bucket.append(text)
        if len(bucket) > _PREFERENCES_CAP:
            del bucket[: len(bucket) - _PREFERENCES_CAP]
        return True

    def record_finding(
        self, category: FindingCategory, summary: str, severity: int
    ) -> bool:
        """Append a finding (audit observation). FIFO cap at 20."""
        summary = summary.strip()
        if not summary:
            return False
        finding = Finding(
            category=category, summary=summary, severity=max(1, min(severity, 5))
        )
        if self.findings and (
            self.findings[-1].summary == finding.summary
            and self.findings[-1].category == finding.category
        ):
            return False
        self.findings.append(finding)
        if len(self.findings) > _FINDINGS_CAP:
            del self.findings[: len(self.findings) - _FINDINGS_CAP]
        return True

    def record_constraint(self, text: str) -> bool:
        """Append a learned constraint (lesson from a Discord error). FIFO cap 30."""
        text = text.strip()
        if not text:
            return False
        if text in self.learned_constraints:
            # Move-to-end semantics: re-confirm the constraint without
            # duplicating, so older lessons get evicted first.
            self.learned_constraints.remove(text)
        self.learned_constraints.append(text)
        if len(self.learned_constraints) > _LEARNED_CONSTRAINTS_CAP:
            del self.learned_constraints[
                : len(self.learned_constraints) - _LEARNED_CONSTRAINTS_CAP
            ]
        return True


def load(guild_id: int) -> GuildContext | None:
    path = DATA_DIR / f"{guild_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return GuildContext.model_validate(data)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to load guild context for %d: %s", guild_id, exc)
        return None


def save(ctx: GuildContext) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{ctx.guild_id}.json"
    path.write_text(ctx.model_dump_json(indent=2), encoding="utf-8")
