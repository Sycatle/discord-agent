"""AutoMod rule parameter models.

The ``actions`` list uses string-encoded entries:

- ``"block_message"``
- ``"send_alert:<channel name or ID>"``
- ``"timeout:<duration in seconds>"``

This stays a flat ``list[str]`` rather than a richer nested model so the
LLM-facing JSON Schema stays readable.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EventType = Literal["message_send", "member_update"]
TriggerType = Literal["keyword", "spam", "keyword_preset", "mention_spam"]
AutoModPreset = Literal["profanity", "sexual_content", "slurs"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateAutoModRuleParams(_Strict):
    """Create an AutoMod rule (keyword filter, spam, excessive mentions)."""

    name: str = Field(description="Rule name")
    event_type: EventType = Field(description="Watched event")
    trigger_type: TriggerType = Field(description="Trigger type")
    keyword_filter: list[str] | None = Field(
        default=None,
        description="Keywords to block for the 'keyword' trigger (optional)",
    )
    regex_patterns: list[str] | None = Field(
        default=None,
        description="Regex patterns for the 'keyword' trigger (optional)",
    )
    allow_list: list[str] | None = Field(default=None, description="Allow-listed words (optional)")
    presets: list[AutoModPreset] | None = Field(
        default=None,
        description="Built-in presets for the 'keyword_preset' trigger (optional)",
    )
    mention_limit: int | None = Field(
        default=None, description="Mention limit for 'mention_spam' (optional)"
    )
    mention_raid_protection: bool | None = Field(
        default=None,
        description="Enable raid mention protection for 'mention_spam' (optional)",
    )
    actions: list[str] = Field(
        description=(
            "Encoded actions list. Each entry is one of: 'block_message', "
            "'send_alert:<channel>', 'timeout:<seconds>'."
        )
    )
    exempt_roles: list[str] | None = Field(
        default=None,
        max_length=20,
        description="Exempt roles (names or IDs), max 20 (optional)",
    )
    exempt_channels: list[str] | None = Field(
        default=None,
        max_length=50,
        description="Exempt channels (names or IDs), max 50 (optional)",
    )
    enabled: bool | None = Field(
        default=None, description="Enable the rule (default false) (optional)"
    )


class EditAutoModRuleParams(_Strict):
    """Edit an existing AutoMod rule."""

    rule: str = Field(description="Rule name or ID")
    name: str | None = Field(default=None, description="New name (optional)")
    enabled: bool | None = Field(default=None, description="Enable/disable (optional)")
    keyword_filter: list[str] | None = Field(default=None, description="New keywords (optional)")
    actions: list[str] | None = Field(
        default=None,
        description=("New encoded actions list. Same format as create_automod_rule (optional)."),
    )
    exempt_roles: list[str] | None = Field(default=None, description="Exempt roles (optional)")
    exempt_channels: list[str] | None = Field(
        default=None, description="Exempt channels (optional)"
    )


class DeleteAutoModRuleParams(_Strict):
    """Delete an AutoMod rule."""

    rule: str = Field(description="Rule name or ID")
