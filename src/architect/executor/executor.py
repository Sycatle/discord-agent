import discord


class Executor:
    async def execute(self, tool_name: str, params: dict, guild: discord.Guild) -> str:
        """Execute a single tool call and return a result string."""
        match tool_name:
            case "create_category":
                name = params["name"]
                await guild.create_category(name=name)
                return f"Category created: {name}"

            case "create_text_channel":
                name = params["name"]
                category = self._resolve_category(guild, params.get("category"))
                await guild.create_text_channel(name=name, category=category)
                return f"Text channel created: #{name}"

            case "create_voice_channel":
                name = params["name"]
                category = self._resolve_category(guild, params.get("category"))
                await guild.create_voice_channel(name=name, category=category)
                return f"Voice channel created: {name}"

            case "create_role":
                name = params["name"]
                color_val = params.get("color")
                color = self._parse_color(color_val)
                mentionable = params.get("mentionable", False)
                await guild.create_role(name=name, color=color, mentionable=mentionable)
                return f"Role created: @{name}"

            case "set_channel_permissions":
                channel_name = params["channel"]
                role_name = params["role"]
                overwrite_data = params.get("overwrite", {})

                channel = discord.utils.get(guild.channels, name=channel_name)
                if channel is None:
                    raise ValueError(f"Channel not found: {channel_name!r}")

                role = discord.utils.get(guild.roles, name=role_name)
                if role is None:
                    raise ValueError(f"Role not found: {role_name!r}")

                overwrite = discord.PermissionOverwrite(**overwrite_data)
                await channel.set_permissions(role, overwrite=overwrite)
                return f"Permissions set: #{channel_name} → @{role_name}"

            case "list_channels":
                categories = ", ".join(c.name for c in guild.categories)
                text_channels = ", ".join(f"#{c.name}" for c in guild.text_channels)
                voice_channels = ", ".join(c.name for c in guild.voice_channels)
                return (
                    f"Categories: {categories}\n"
                    f"Text channels: {text_channels}\n"
                    f"Voice channels: {voice_channels}"
                )

            case "list_roles":
                roles = ", ".join(
                    r.name for r in guild.roles if r.name != "@everyone"
                )
                return f"Roles: {roles}"

            case _:
                raise NotImplementedError(f"No handler for tool: {tool_name!r}")

    def _resolve_category(
        self, guild: discord.Guild, category_name: str | None
    ) -> discord.CategoryChannel | None:
        if category_name is None:
            return None
        return discord.utils.get(guild.categories, name=category_name)

    def _parse_color(self, color_val) -> discord.Color:
        if color_val is None:
            return discord.Color.default()
        if isinstance(color_val, int):
            return discord.Color(color_val)
        if isinstance(color_val, str):
            hex_str = color_val.lstrip("#")
            return discord.Color(int(hex_str, 16))
        return discord.Color.default()
