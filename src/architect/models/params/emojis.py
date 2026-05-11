"""Emoji and sticker parameter models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateEmojiParams(_Strict):
    """Upload a custom emoji from a publicly accessible image URL.

    The image must be PNG/JPG/GIF, max 256 KB, max 128x128 px.
    """

    name: str = Field(
        description="Emoji name (2-32 chars, alphanumeric + underscore)",
        min_length=2,
        max_length=32,
    )
    image_url: str = Field(description="Publicly accessible image URL")
    roles_allowed: list[str] | None = Field(
        default=None,
        description="Restrict usage to these role names (optional)",
    )
    reason: str | None = Field(default=None, description="Audit-log reason")


class DeleteEmojiParams(_Strict):
    """Delete a custom emoji by name. IRREVERSIBLE."""

    emoji_name: str = Field(description="Emoji name (without colons)")
    reason: str | None = Field(default=None, description="Audit-log reason")


class RenameEmojiParams(_Strict):
    """Rename a custom emoji."""

    old_name: str = Field(description="Current emoji name")
    new_name: str = Field(
        description="New emoji name (2-32 chars)",
        min_length=2,
        max_length=32,
    )
    reason: str | None = Field(default=None, description="Audit-log reason")


class DeleteStickerParams(_Strict):
    """Delete a custom sticker by name. IRREVERSIBLE."""

    sticker_name: str = Field(description="Sticker name")
    reason: str | None = Field(default=None, description="Audit-log reason")
