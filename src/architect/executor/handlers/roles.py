"""Role-domain handlers."""

from __future__ import annotations

import discord

from architect.executor._resolve import parse_color, parse_member, resolve_role
from architect.models.params.roles import (
    AssignRoleParams,
    CreateRoleParams,
    DeleteRoleParams,
    EditRoleParams,
    RemoveRoleParams,
)


async def create_role(params: CreateRoleParams, guild: discord.Guild) -> str:
    color = parse_color(params.color)
    mentionable = bool(params.mentionable)
    await guild.create_role(name=params.name, color=color, mentionable=mentionable)
    return f"Role created: @{params.name}"


async def edit_role(params: EditRoleParams, guild: discord.Guild) -> str:
    role = resolve_role(guild, params.role)
    kwargs: dict = {}
    if params.name is not None:
        kwargs["name"] = params.name
    if params.color is not None:
        kwargs["color"] = parse_color(params.color)
    if params.hoist is not None:
        kwargs["hoist"] = params.hoist
    if params.mentionable is not None:
        kwargs["mentionable"] = params.mentionable
    await role.edit(**kwargs)
    return f"Role updated: @{role.name}"


async def delete_role(params: DeleteRoleParams, guild: discord.Guild) -> str:
    role = resolve_role(guild, params.role)
    name = role.name
    await role.delete(reason=params.reason)
    return f"Role deleted: @{name}"


async def assign_role(params: AssignRoleParams, guild: discord.Guild) -> str:
    member = parse_member(guild, params.user)
    if member is None:
        raise ValueError(f"Member not found: {params.user!r}")
    role = resolve_role(guild, params.role)
    await member.add_roles(role)
    return f"Role @{role.name} assigned to {params.user}"


async def remove_role(params: RemoveRoleParams, guild: discord.Guild) -> str:
    member = parse_member(guild, params.user)
    if member is None:
        raise ValueError(f"Member not found: {params.user!r}")
    role = resolve_role(guild, params.role)
    await member.remove_roles(role)
    return f"Role @{role.name} removed from {params.user}"
