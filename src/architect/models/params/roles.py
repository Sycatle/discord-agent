"""Role-related parameter models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateRoleParams(_Strict):
    """Create a Discord role."""

    name: str = Field(description="Role name")
    color: str | int | None = Field(
        default=None, description="Hex color string or int, e.g. '#3498DB' (optional)"
    )
    mentionable: bool | None = Field(
        default=None, description="Whether the role is mentionable (optional)"
    )


class EditRoleParams(_Strict):
    """Edit an existing role (name, color, hoist, mentionable). Forbidden on @everyone."""

    role: str = Field(description="Role name or ID")
    name: str | None = Field(default=None, description="New name (optional)")
    color: str | None = Field(default=None, description="Hex color '#RRGGBB' (optional)")
    hoist: bool | None = Field(
        default=None,
        description="Display separately in the member list (optional)",
    )
    mentionable: bool | None = Field(default=None, description="Allow @mentions (optional)")


class DeleteRoleParams(_Strict):
    """Delete a role. IRREVERSIBLE. Forbidden on @everyone."""

    role: str = Field(description="Role name or ID")
    reason: str | None = Field(default=None, description="Reason (optional)")


class AssignRoleParams(_Strict):
    """Assign a role to a member (via @mention or user_id)."""

    user: str = Field(description="@mention or numeric user_id")
    role: str = Field(description="Role name or ID")


class RemoveRoleParams(_Strict):
    """Remove a role from a member."""

    user: str = Field(description="@mention or numeric user_id")
    role: str = Field(description="Role name or ID")
