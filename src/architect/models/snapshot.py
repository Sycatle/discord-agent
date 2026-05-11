"""Structured guild snapshot used by the validator and the diff preview.

A snapshot is a plain-data view of a Discord guild built once per user turn
(in ``bot/events._build_guild_snapshot``) and reused for:

- pre-validation of a plan (``executor/validator``)
- the diff-style plan preview (``bot/views.PlanView.build_embed``)

Keeping it as a dataclass (not a Pydantic model) makes it cheap to build
from ``discord.Guild`` and easy to construct in tests without a live
Discord connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ChannelInfo:
    id: int
    name: str
    type: str  # "text" | "voice" | "forum" | "stage" | "category"
    parent_id: int | None = None
    position: int = 0


@dataclass(frozen=True, slots=True)
class RoleInfo:
    id: int
    name: str
    position: int


@dataclass(frozen=True, slots=True)
class AutoModRuleInfo:
    id: int
    name: str
    trigger_type: str  # "keyword" | "spam" | "keyword_preset" | "mention_spam"


@dataclass(slots=True)
class GuildSnapshot:
    categories: list[ChannelInfo] = field(default_factory=list)
    channels: list[ChannelInfo] = field(default_factory=list)  # non-category
    roles: list[RoleInfo] = field(default_factory=list)
    automod_rules: list[AutoModRuleInfo] = field(default_factory=list)
    bot_top_role_position: int = 0  # 0 when unknown

    def category_by_name(self, name: str) -> ChannelInfo | None:
        for c in self.categories:
            if c.name == name or str(c.id) == name:
                return c
        return None

    def channel_by_name(self, name: str) -> ChannelInfo | None:
        for c in self.channels:
            if c.name == name or str(c.id) == name:
                return c
        for c in self.categories:
            if c.name == name or str(c.id) == name:
                return c
        return None

    def role_by_name(self, name: str) -> RoleInfo | None:
        for r in self.roles:
            if r.name == name or str(r.id) == name:
                return r
        return None
