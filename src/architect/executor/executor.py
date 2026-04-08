import discord

from ..models.actions import ActionType
from ..models.plan import Plan


class Executor:
    async def execute(self, plan: Plan, guild: discord.Guild) -> list[str]:
        results = []
        for action in plan.actions:
            result = await self._dispatch(action, guild)
            results.append(result)
        return results

    async def _dispatch(self, action, guild: discord.Guild) -> str:
        p = action.params
        match action.type:
            case ActionType.CREATE_CATEGORY:
                cat = await guild.create_category(name=p["name"])
                return f"Catégorie créée : {cat.name}"

            case ActionType.CREATE_TEXT_CHANNEL:
                category = discord.utils.get(guild.categories, name=p.get("category"))
                ch = await guild.create_text_channel(name=p["name"], category=category)
                return f"Salon texte créé : #{ch.name}"

            case ActionType.CREATE_VOICE_CHANNEL:
                category = discord.utils.get(guild.categories, name=p.get("category"))
                ch = await guild.create_voice_channel(name=p["name"], category=category)
                return f"Salon vocal créé : {ch.name}"

            case ActionType.CREATE_ROLE:
                role = await guild.create_role(
                    name=p["name"],
                    color=discord.Color(int(p.get("color", "0x000000"), 16)),
                    mentionable=p.get("mentionable", False),
                )
                return f"Rôle créé : @{role.name}"

            case ActionType.SET_CHANNEL_PERMISSIONS:
                channel = discord.utils.get(guild.channels, name=p["channel"])
                role = discord.utils.get(guild.roles, name=p["role"])
                overwrite = discord.PermissionOverwrite(**p.get("permissions", {}))
                await channel.set_permissions(role, overwrite=overwrite)
                return f"Permissions définies : #{p['channel']} → @{p['role']}"
