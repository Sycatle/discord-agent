from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

import discord

logger = logging.getLogger(__name__)


# Permission requise par tool. Vérifiée avant l'appel Discord pour produire un
# message clair au lieu d'un 403. Les tools read-only sont absents → pas de check.
_REQUIRED_PERMISSIONS: dict[str, str] = {
    "create_category": "manage_channels",
    "create_text_channel": "manage_channels",
    "create_voice_channel": "manage_channels",
    "create_forum_channel": "manage_channels",
    "create_stage_channel": "manage_channels",
    "edit_channel": "manage_channels",
    "delete_channel": "manage_channels",
    "set_channel_permissions": "manage_channels",
    "create_invite": "create_instant_invite",
    "delete_invite": "manage_channels",
    "create_webhook": "manage_webhooks",
    "edit_webhook": "manage_webhooks",
    "delete_webhook": "manage_webhooks",
    "create_role": "manage_roles",
    "edit_role": "manage_roles",
    "delete_role": "manage_roles",
    "assign_role": "manage_roles",
    "remove_role": "manage_roles",
    "edit_member": "moderate_members",
    "create_scheduled_event": "manage_events",
    "edit_scheduled_event": "manage_events",
    "delete_scheduled_event": "manage_events",
    "create_automod_rule": "manage_guild",
    "edit_automod_rule": "manage_guild",
    "delete_automod_rule": "manage_guild",
    "edit_server": "manage_guild",
    "edit_welcome_screen": "manage_guild",
}


# Pour le mode atomic batch : à chaque action create_* qu'on sait inverser
# déterministiquement, on associe l'action de suppression et la traduction
# des paramètres. Les actions sans entrée ici (create_invite, edit_*, etc.)
# ne sont pas rollback-ables et seront ignorées par le rollback.
ROLLBACK_ACTIONS: dict[str, tuple[str, dict[str, str]]] = {
    "create_category": ("delete_channel", {"channel": "name"}),
    "create_text_channel": ("delete_channel", {"channel": "name"}),
    "create_voice_channel": ("delete_channel", {"channel": "name"}),
    "create_forum_channel": ("delete_channel", {"channel": "name"}),
    "create_stage_channel": ("delete_channel", {"channel": "name"}),
    "create_role": ("delete_role", {"role": "name"}),
    "create_webhook": ("delete_webhook", {"webhook": "name"}),
    "create_scheduled_event": ("delete_scheduled_event", {"event": "name"}),
    "create_automod_rule": ("delete_automod_rule", {"rule": "name"}),
}


class ExecuteError(Exception):
    """Erreur métier (permission manquante, Discord 403/404/HTTPException).

    Levée par execute(strict=True) pour permettre au batch coordinator de
    distinguer succès et échec — le mode non-strict retourne le message
    en string pour rester compatible avec la boucle agentic.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Executor:
    async def execute(
        self,
        tool_name: str,
        params: dict,
        guild: discord.Guild,
        *,
        strict: bool = False,
    ) -> str:
        """Execute a single tool call and return a result string.

        Wraps Discord API errors (Forbidden/NotFound/HTTPException) into
        readable messages and pre-checks bot permissions for mutating tools.

        En mode strict=True, les erreurs Discord et permissions sont relevées
        comme ExecuteError au lieu d'être retournées sous forme de string —
        utilisé par _execute_batch pour comptabiliser correctement les échecs.
        """
        required = _REQUIRED_PERMISSIONS.get(tool_name)
        if required is not None and guild.me is not None:
            if not getattr(guild.me.guild_permissions, required, False):
                msg = f"Permission manquante : `{required}`. Le bot ne peut pas exécuter `{tool_name}`."
                if strict:
                    raise ExecuteError(msg)
                return msg

        try:
            return await self._dispatch(tool_name, params, guild)
        except discord.Forbidden as e:
            logger.warning("Discord Forbidden on %s: %s", tool_name, e)
            msg = f"Action refusée par Discord (permissions ou hiérarchie) : `{tool_name}`."
            if strict:
                raise ExecuteError(msg) from e
            return msg
        except discord.NotFound as e:
            logger.warning("Discord NotFound on %s: %s", tool_name, e)
            msg = f"Entité introuvable (peut-être supprimée entre la preview et l'exécution) : `{tool_name}`."
            if strict:
                raise ExecuteError(msg) from e
            return msg
        except discord.HTTPException as e:
            logger.exception("Discord HTTPException on %s", tool_name)
            msg = f"Erreur Discord ({e.status}) sur `{tool_name}` : {e.text or e}"
            if strict:
                raise ExecuteError(msg) from e
            return msg

    async def _dispatch(self, tool_name: str, params: dict, guild: discord.Guild) -> str:
        match tool_name:
            # ── Existing ──────────────────────────────────────────────────────
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
                color = self._parse_color(params.get("color"))
                mentionable = params.get("mentionable", False)
                await guild.create_role(name=name, color=color, mentionable=mentionable)
                return f"Role created: @{name}"

            case "set_channel_permissions":
                channel_name = params["channel"]
                role_name = params["role"]
                channel = discord.utils.get(guild.channels, name=channel_name)
                if channel is None:
                    raise ValueError(f"Channel not found: {channel_name!r}")
                role = discord.utils.get(guild.roles, name=role_name)
                if role is None:
                    raise ValueError(f"Role not found: {role_name!r}")
                overwrite_kwargs: dict[str, bool] = {}
                for perm in params.get("allow") or []:
                    overwrite_kwargs[perm] = True
                for perm in params.get("deny") or []:
                    overwrite_kwargs[perm] = False
                overwrite = discord.PermissionOverwrite(**overwrite_kwargs)
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
                roles = ", ".join(r.name for r in guild.roles if r.name != "@everyone")
                return f"Roles: {roles}"

            # ── Domain 1 — Channels ───────────────────────────────────────────
            case "create_forum_channel":
                name = params["name"]
                category = self._resolve_category(guild, params.get("category"))
                kwargs: dict = {"name": name}
                if category:
                    kwargs["category"] = category
                if (v := params.get("topic")) is not None:
                    kwargs["topic"] = v
                if (v := params.get("slowmode")) is not None:
                    kwargs["slowmode_delay"] = v
                if (v := params.get("nsfw")) is not None:
                    kwargs["nsfw"] = v
                if params.get("available_tags"):
                    kwargs["available_tags"] = [
                        discord.ForumTag(name=t) for t in params["available_tags"]
                    ]
                if params.get("require_tag") is not None:
                    kwargs["require_tag"] = params["require_tag"]
                if (v := params.get("default_sort_order")) is not None:
                    sort_map = {
                        "latest_activity": discord.ForumOrderType.latest_activity,
                        "creation_date": discord.ForumOrderType.creation_date,
                    }
                    kwargs["default_sort_order"] = sort_map[v]
                if (v := params.get("default_forum_layout")) is not None:
                    layout_map = {
                        "list": discord.ForumLayoutType.list_view,
                        "gallery": discord.ForumLayoutType.gallery_view,
                    }
                    kwargs["default_layout"] = layout_map[v]
                await guild.create_forum(**kwargs)
                return f"Forum channel created: #{name}"

            case "create_stage_channel":
                name = params["name"]
                category = self._resolve_category(guild, params.get("category"))
                kwargs = {"name": name}
                if category:
                    kwargs["category"] = category
                for key in ("bitrate", "user_limit", "rtc_region", "position"):
                    if (v := params.get(key)) is not None:
                        kwargs[key] = v
                await guild.create_stage_channel(**kwargs)
                return f"Stage channel created: {name}"

            case "edit_channel":
                ch_ref = params["channel"]
                channel = self._resolve_channel(guild, ch_ref)
                if channel is None:
                    raise ValueError(f"Channel not found: {ch_ref!r}")
                kwargs = {}
                if (v := params.get("name")) is not None:
                    kwargs["name"] = v
                if (v := params.get("topic")) is not None:
                    kwargs["topic"] = v
                if (v := params.get("slowmode")) is not None:
                    kwargs["slowmode_delay"] = v
                if (v := params.get("nsfw")) is not None:
                    kwargs["nsfw"] = v
                if (v := params.get("position")) is not None:
                    kwargs["position"] = v
                if (v := params.get("bitrate")) is not None:
                    kwargs["bitrate"] = v
                if (v := params.get("user_limit")) is not None:
                    kwargs["user_limit"] = v
                if (v := params.get("rtc_region")) is not None:
                    kwargs["rtc_region"] = v
                if (v := params.get("video_quality_mode")) is not None:
                    kwargs["video_quality_mode"] = discord.VideoQualityMode[v]
                if (v := params.get("parent_id")) is not None:
                    kwargs["category"] = self._resolve_category(guild, v)
                if (v := params.get("default_auto_archive_duration")) is not None:
                    kwargs["default_auto_archive_duration"] = v
                await channel.edit(**kwargs)
                return f"Channel updated: {ch_ref}"

            case "delete_channel":
                ch_ref = params["channel"]
                channel = self._resolve_channel(guild, ch_ref)
                if channel is None:
                    raise ValueError(f"Channel not found: {ch_ref!r}")
                rules_ch = getattr(guild, "rules_channel", None)
                if rules_ch is not None and channel.id == rules_ch.id:
                    raise ValueError(f"Cannot delete the rules channel: {ch_ref!r}")
                await channel.delete(reason=params.get("reason"))
                return f"Channel deleted: {ch_ref}"

            case "create_invite":
                ch_ref = params["channel"]
                channel = self._resolve_channel(guild, ch_ref)
                if channel is None:
                    raise ValueError(f"Channel not found: {ch_ref!r}")
                kwargs = {}
                if (v := params.get("max_age")) is not None:
                    kwargs["max_age"] = v
                if (v := params.get("max_uses")) is not None:
                    kwargs["max_uses"] = v
                if (v := params.get("temporary")) is not None:
                    kwargs["temporary"] = v
                invite = await channel.create_invite(**kwargs)
                return f"Invite created: {invite.url}"

            case "delete_invite":
                code = params["code"]
                invites = await guild.invites()
                invite = next((i for i in invites if i.code == code), None)
                if invite is None:
                    raise ValueError(f"Invite not found: {code!r}")
                await invite.delete()
                return f"Invite revoked: {code}"

            case "create_webhook":
                ch_ref = params["channel"]
                channel = self._resolve_channel(guild, ch_ref)
                if channel is None:
                    raise ValueError(f"Channel not found: {ch_ref!r}")
                webhook = await channel.create_webhook(name=params["name"])
                return f"Webhook created: {webhook.name} in #{ch_ref}"

            case "edit_webhook":
                wh_ref = params["webhook"]
                webhook = await self._resolve_webhook(guild, wh_ref)
                if webhook is None:
                    raise ValueError(f"Webhook not found: {wh_ref!r}")
                kwargs = {}
                if (v := params.get("name")) is not None:
                    kwargs["name"] = v
                if (v := params.get("channel")) is not None:
                    target_ch = self._resolve_channel(guild, v)
                    if target_ch is None:
                        raise ValueError(f"Channel not found: {v!r}")
                    kwargs["channel"] = target_ch
                await webhook.edit(**kwargs)
                return f"Webhook updated: {wh_ref}"

            case "delete_webhook":
                wh_ref = params["webhook"]
                webhook = await self._resolve_webhook(guild, wh_ref)
                if webhook is None:
                    raise ValueError(f"Webhook not found: {wh_ref!r}")
                await webhook.delete()
                return f"Webhook deleted: {wh_ref}"

            # ── Domain 2 — Roles ──────────────────────────────────────────────
            case "edit_role":
                role = self._resolve_role(guild, params["role"])
                kwargs = {}
                if (v := params.get("name")) is not None:
                    kwargs["name"] = v
                if (v := params.get("color")) is not None:
                    kwargs["color"] = self._parse_color(v)
                if (v := params.get("hoist")) is not None:
                    kwargs["hoist"] = v
                if (v := params.get("mentionable")) is not None:
                    kwargs["mentionable"] = v
                await role.edit(**kwargs)
                return f"Role updated: @{role.name}"

            case "delete_role":
                role = self._resolve_role(guild, params["role"])
                name = role.name
                await role.delete(reason=params.get("reason"))
                return f"Role deleted: @{name}"

            case "assign_role":
                member = self._parse_member(guild, params["user"])
                if member is None:
                    raise ValueError(f"Member not found: {params['user']!r}")
                role = self._resolve_role(guild, params["role"])
                await member.add_roles(role)
                return f"Role @{role.name} assigned to {params['user']}"

            case "remove_role":
                member = self._parse_member(guild, params["user"])
                if member is None:
                    raise ValueError(f"Member not found: {params['user']!r}")
                role = self._resolve_role(guild, params["role"])
                await member.remove_roles(role)
                return f"Role @{role.name} removed from {params['user']}"

            # ── Domain 3 — Members ────────────────────────────────────────────
            case "edit_member":
                member = self._parse_member(guild, params["user"])
                if member is None:
                    raise ValueError(f"Member not found: {params['user']!r}")
                kwargs = {}
                if "nick" in params:
                    kwargs["nick"] = params["nick"]  # None = reset
                if (v := params.get("mute")) is not None:
                    kwargs["mute"] = v
                if (v := params.get("deaf")) is not None:
                    kwargs["deafen"] = v
                if "timeout_until" in params:
                    raw = params["timeout_until"]
                    kwargs["communication_disabled_until"] = (
                        datetime.fromisoformat(raw) if raw else None
                    )
                if (v := params.get("move_to_channel")) is not None:
                    ch = self._resolve_channel(guild, v)
                    if ch is None:
                        raise ValueError(f"Voice channel not found: {v!r}")
                    kwargs["voice_channel"] = ch
                await member.edit(**kwargs)
                return f"Member {params['user']} updated"

            # ── Domain 4 — Scheduled Events ───────────────────────────────────
            case "create_scheduled_event":
                entity_type_map = {
                    "voice": discord.EntityType.voice,
                    "stage": discord.EntityType.stage_instance,
                    "external": discord.EntityType.external,
                }
                entity_type = entity_type_map[params["entity_type"]]
                start = datetime.fromisoformat(params["start_time"])
                end = (
                    datetime.fromisoformat(params["end_time"])
                    if params.get("end_time")
                    else None
                )
                kwargs = {
                    "name": params["name"],
                    "start_time": start,
                    "privacy_level": discord.PrivacyLevel.guild_only,
                    "entity_type": entity_type,
                }
                if end:
                    kwargs["end_time"] = end
                if params.get("description"):
                    kwargs["description"] = params["description"]
                if entity_type == discord.EntityType.external:
                    kwargs["location"] = params["location"]
                else:
                    ch = self._resolve_channel(guild, params["channel"])
                    if ch is None:
                        raise ValueError(f"Channel not found: {params['channel']!r}")
                    kwargs["channel"] = ch
                event = await guild.create_scheduled_event(**kwargs)
                return f"Scheduled event created: {event.name}"

            case "edit_scheduled_event":
                event = self._resolve_scheduled_event(guild, params["event"])
                if event is None:
                    raise ValueError(f"Scheduled event not found: {params['event']!r}")
                kwargs = {}
                for key in ("name", "description"):
                    if (v := params.get(key)) is not None:
                        kwargs[key] = v
                if (v := params.get("start_time")) is not None:
                    kwargs["start_time"] = datetime.fromisoformat(v)
                if (v := params.get("end_time")) is not None:
                    kwargs["end_time"] = datetime.fromisoformat(v)
                if (v := params.get("status")) is not None:
                    status_map = {
                        "active": discord.EventStatus.active,
                        "completed": discord.EventStatus.completed,
                        "canceled": discord.EventStatus.canceled,
                    }
                    kwargs["status"] = status_map[v]
                await event.edit(**kwargs)
                return f"Event updated: {params['event']}"

            case "delete_scheduled_event":
                event = self._resolve_scheduled_event(guild, params["event"])
                if event is None:
                    raise ValueError(f"Scheduled event not found: {params['event']!r}")
                await event.delete()
                return f"Event deleted: {params['event']}"

            # ── Domain 5 — AutoMod ────────────────────────────────────────────
            case "create_automod_rule":
                trigger = self._build_automod_trigger(params)
                actions = self._build_automod_actions(guild, params["actions"])
                event_type_map = {
                    "message_send": discord.AutoModRuleEventType.message_send,
                    "member_update": discord.AutoModRuleEventType.member_update,
                }
                kwargs = {
                    "name": params["name"],
                    "event_type": event_type_map[params["event_type"]],
                    "trigger": trigger,
                    "actions": actions,
                    "enabled": params.get("enabled", False),
                }
                exempt_roles = [
                    self._resolve_role(guild, r) for r in (params.get("exempt_roles") or [])
                ]
                exempt_channels = [
                    c for r in (params.get("exempt_channels") or [])
                    if (c := self._resolve_channel(guild, r)) is not None
                ]
                if exempt_roles:
                    kwargs["exempt_roles"] = [r for r in exempt_roles if r]
                if exempt_channels:
                    kwargs["exempt_channels"] = exempt_channels
                rule = await guild.create_automod_rule(**kwargs)
                return f"AutoMod rule created: {rule.name}"

            case "edit_automod_rule":
                rule_ref = params["rule"]
                rules = await guild.fetch_auto_moderation_rules()
                rule = next(
                    (r for r in rules if str(r.id) == rule_ref or r.name == rule_ref),
                    None,
                )
                if rule is None:
                    raise ValueError(f"AutoMod rule not found: {rule_ref!r}")
                kwargs = {}
                if (v := params.get("name")) is not None:
                    kwargs["name"] = v
                if (v := params.get("enabled")) is not None:
                    kwargs["enabled"] = v
                if params.get("actions"):
                    kwargs["actions"] = self._build_automod_actions(guild, params["actions"])
                if params.get("exempt_roles") is not None:
                    kwargs["exempt_roles"] = [
                        r for n in params["exempt_roles"]
                        if (r := self._resolve_role(guild, n))
                    ]
                if params.get("exempt_channels") is not None:
                    kwargs["exempt_channels"] = [
                        c for n in params["exempt_channels"]
                        if (c := self._resolve_channel(guild, n)) is not None
                    ]
                await rule.edit(**kwargs)
                return f"AutoMod rule updated: {rule_ref}"

            case "delete_automod_rule":
                rule_ref = params["rule"]
                rules = await guild.fetch_auto_moderation_rules()
                rule = next(
                    (r for r in rules if str(r.id) == rule_ref or r.name == rule_ref),
                    None,
                )
                if rule is None:
                    raise ValueError(f"AutoMod rule not found: {rule_ref!r}")
                await rule.delete()
                return f"AutoMod rule deleted: {rule_ref}"

            # ── Domain 6 — Server Settings ────────────────────────────────────
            case "edit_server":
                kwargs = {}
                if (v := params.get("name")) is not None:
                    kwargs["name"] = v
                if (v := params.get("verification_level")) is not None:
                    kwargs["verification_level"] = discord.VerificationLevel[v]
                if (v := params.get("default_message_notifications")) is not None:
                    notif_map = {
                        "all_messages": discord.NotificationLevel.all_messages,
                        "only_mentions": discord.NotificationLevel.only_mentions,
                    }
                    kwargs["default_notifications"] = notif_map[v]
                if (v := params.get("explicit_content_filter")) is not None:
                    filter_map = {
                        "disabled": discord.ContentFilter.disabled,
                        "members_without_roles": discord.ContentFilter.no_role,
                        "all_members": discord.ContentFilter.all_members,
                    }
                    kwargs["explicit_content_filter"] = filter_map[v]
                if "afk_channel" in params:
                    raw = params["afk_channel"]
                    kwargs["afk_channel"] = self._resolve_channel(guild, raw) if raw else None
                if (v := params.get("afk_timeout")) is not None:
                    kwargs["afk_timeout"] = v
                for ch_param, kw in (
                    ("system_channel", "system_channel"),
                    ("rules_channel", "rules_channel"),
                    ("public_updates_channel", "public_updates_channel"),
                    ("safety_alerts_channel", "safety_alerts_channel"),
                ):
                    if ch_param in params:
                        raw = params[ch_param]
                        kwargs[kw] = self._resolve_channel(guild, raw) if raw else None
                if (v := params.get("description")) is not None:
                    kwargs["description"] = v
                if (v := params.get("preferred_locale")) is not None:
                    # Locale values are BCP-47 tags (e.g. "fr", "en-US")
                    # discord.Locale enum members use value-based lookup
                    kwargs["preferred_locale"] = discord.Locale(v.replace("_", "-"))
                if (v := params.get("premium_progress_bar_enabled")) is not None:
                    kwargs["premium_progress_bar_enabled"] = v
                if (v := params.get("community")) is not None:
                    if v is True:
                        rules_ch = kwargs.get("rules_channel") or params.get("rules_channel")
                        updates_ch = kwargs.get("public_updates_channel") or params.get("public_updates_channel")
                        if not rules_ch or not updates_ch:
                            raise ValueError(
                                "community mode requires rules_channel and public_updates_channel"
                            )
                    kwargs["community"] = v
                await guild.edit(**kwargs)
                return "Server settings updated"

            # ── Domain 7 — Welcome Screen ─────────────────────────────────────
            case "edit_welcome_screen":
                kwargs = {}
                if (v := params.get("enabled")) is not None:
                    kwargs["enabled"] = v
                if (v := params.get("description")) is not None:
                    kwargs["description"] = v
                if params.get("welcome_channels"):
                    channels = []
                    for wc in params["welcome_channels"]:
                        ch = self._resolve_channel(guild, wc["channel"])
                        if ch is None:
                            raise ValueError(f"Welcome channel not found: {wc['channel']!r}")
                        emoji = discord.PartialEmoji.from_str(wc["emoji"]) if wc.get("emoji") else None
                        channels.append(
                            discord.WelcomeChannel(
                                channel=ch,
                                description=wc["description"],
                                emoji=emoji,
                            )
                        )
                    kwargs["welcome_channels"] = channels
                await guild.edit_welcome_screen(**kwargs)
                return "Welcome screen updated"

            # ── Read-only ─────────────────────────────────────────────────────
            case "get_member_roles":
                member = self._parse_member(guild, params["user"])
                if member is None:
                    raise ValueError(f"Member not found: {params['user']!r}")
                roles = [r.name for r in member.roles if r.name != "@everyone"]
                return f"Roles of {params['user']}: {', '.join(roles) or 'aucun'}"

            case "get_server_info":
                return (
                    f"Serveur: {guild.name}\n"
                    f"Membres: {guild.member_count}\n"
                    f"Vérification: {guild.verification_level}\n"
                    f"Filtre contenu: {guild.explicit_content_filter}\n"
                    f"Notifications: {guild.default_notifications}\n"
                    f"Boost: niveau {guild.premium_tier} ({guild.premium_subscription_count} boosts)\n"
                    f"Locale: {guild.preferred_locale}"
                )

            case "list_invites":
                invites = await guild.invites()
                if not invites:
                    return "Aucune invitation active."
                lines = [
                    f"- {i.code} → #{i.channel.name if i.channel else '?'} "
                    f"({i.uses}/{i.max_uses or '∞'} utilisations)"
                    for i in invites
                ]
                return "Invitations:\n" + "\n".join(lines)

            case "list_webhooks":
                webhooks = await guild.webhooks()
                if not webhooks:
                    return "Aucun webhook."
                lines = [f"- {w.name} → #{w.channel.name if w.channel else '?'}" for w in webhooks]
                return "Webhooks:\n" + "\n".join(lines)

            case "list_scheduled_events":
                events = guild.scheduled_events
                if not events:
                    return "Aucun événement planifié."
                lines = [f"- {e.name} ({e.entity_type}) — {e.start_time}" for e in events]
                return "Événements:\n" + "\n".join(lines)

            case "check_bot_permissions":
                me = guild.me
                if me is None:
                    return "Impossible de récupérer les permissions du bot (membership manquant)."
                perms = me.guild_permissions
                # Liste unique des permissions requises sur l'ensemble des tools
                required_perms = sorted(set(_REQUIRED_PERMISSIONS.values()))
                granted = [p for p in required_perms if getattr(perms, p, False)]
                missing = [p for p in required_perms if not getattr(perms, p, False)]
                lines = [f"Permissions accordées : {', '.join(granted) or 'aucune'}"]
                if missing:
                    lines.append(f"Permissions manquantes : {', '.join(missing)}")
                else:
                    lines.append("Toutes les permissions requises sont présentes.")
                return "\n".join(lines)

            case "list_automod_rules":
                rules = await guild.fetch_auto_moderation_rules()
                if not rules:
                    return "Aucune règle AutoMod."
                lines = [f"- {r.name} ({'activée' if r.enabled else 'désactivée'})" for r in rules]
                return "Règles AutoMod:\n" + "\n".join(lines)

            case _:
                raise NotImplementedError(f"No handler for tool: {tool_name!r}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _resolve_channel(
        self, guild: discord.Guild, name_or_id: str
    ) -> discord.abc.GuildChannel | None:
        try:
            ch = guild.get_channel(int(name_or_id))
            if ch is not None:
                return ch
        except (ValueError, TypeError):
            pass
        return discord.utils.get(guild.channels, name=name_or_id)

    def _resolve_category(
        self, guild: discord.Guild, category_name: str | None
    ) -> discord.CategoryChannel | None:
        if category_name is None:
            return None
        return discord.utils.get(guild.categories, name=category_name)

    def _resolve_role(self, guild: discord.Guild, name_or_id: str) -> discord.Role:
        role: discord.Role | None = None
        try:
            role = guild.get_role(int(name_or_id))
        except (ValueError, TypeError):
            pass
        if role is None:
            role = discord.utils.get(guild.roles, name=name_or_id)
        if role is None:
            raise ValueError(f"Role not found: {name_or_id!r}")
        if role == guild.default_role:
            raise ValueError("Cannot target @everyone")
        return role

    def _parse_member(self, guild: discord.Guild, user_str: str) -> discord.Member | None:
        m = re.match(r"<@!?(\d+)>", user_str.strip())
        user_id = int(m.group(1)) if m else int(user_str.strip())
        return guild.get_member(user_id)

    async def _resolve_webhook(
        self, guild: discord.Guild, name_or_id: str
    ) -> discord.Webhook | None:
        webhooks = await guild.webhooks()
        try:
            wh_id = int(name_or_id)
            return next((w for w in webhooks if w.id == wh_id), None)
        except (ValueError, TypeError):
            return next((w for w in webhooks if w.name == name_or_id), None)

    def _resolve_scheduled_event(
        self, guild: discord.Guild, name_or_id: str
    ) -> discord.ScheduledEvent | None:
        try:
            evt_id = int(name_or_id)
            return next((e for e in guild.scheduled_events if e.id == evt_id), None)
        except (ValueError, TypeError):
            return next((e for e in guild.scheduled_events if e.name == name_or_id), None)

    def _parse_color(self, color_val) -> discord.Color:
        if color_val is None:
            return discord.Color.default()
        if isinstance(color_val, int):
            return discord.Color(color_val)
        if isinstance(color_val, str):
            return discord.Color(int(color_val.lstrip("#"), 16))
        return discord.Color.default()

    def _build_automod_trigger(self, params: dict) -> discord.AutoModTrigger:
        trigger_type_map = {
            "keyword": discord.AutoModRuleTriggerType.keyword,
            "spam": discord.AutoModRuleTriggerType.spam,
            "keyword_preset": discord.AutoModRuleTriggerType.keyword_preset,
            "mention_spam": discord.AutoModRuleTriggerType.mention_spam,
        }
        trigger_type = trigger_type_map[params["trigger_type"]]
        kwargs: dict = {"type": trigger_type}
        if params.get("keyword_filter"):
            kwargs["keyword_filter"] = params["keyword_filter"]
        if params.get("regex_patterns"):
            kwargs["regex_patterns"] = params["regex_patterns"]
        if params.get("allow_list"):
            kwargs["allow_list"] = params["allow_list"]
        if params.get("presets"):
            preset_map = {
                "profanity": discord.AutoModPresets.profanity,
                "sexual_content": discord.AutoModPresets.sexual_content,
                "slurs": discord.AutoModPresets.slurs,
            }
            presets = discord.AutoModPresets.none()
            for p in params["presets"]:
                presets |= preset_map[p]
            kwargs["presets"] = presets
        if params.get("mention_limit") is not None:
            kwargs["mention_limit"] = params["mention_limit"]
        if params.get("mention_raid_protection") is not None:
            kwargs["mention_raid_protection"] = params["mention_raid_protection"]
        return discord.AutoModTrigger(**kwargs)

    def _build_automod_actions(
        self, guild: discord.Guild, actions: list[str]
    ) -> list[discord.AutoModRuleAction]:
        result = []
        for action_str in actions:
            if action_str == "block_message":
                result.append(
                    discord.AutoModRuleAction(
                        type=discord.AutoModRuleActionType.block_message
                    )
                )
            elif action_str.startswith("send_alert:"):
                ch_ref = action_str[len("send_alert:"):]
                ch = self._resolve_channel(guild, ch_ref)
                if ch is None:
                    raise ValueError(f"Alert channel not found: {ch_ref!r}")
                result.append(
                    discord.AutoModRuleAction(
                        type=discord.AutoModRuleActionType.send_alert_message,
                        channel_id=ch.id,
                    )
                )
            elif action_str.startswith("timeout:"):
                duration_seconds = int(action_str[len("timeout:"):])
                result.append(
                    discord.AutoModRuleAction(
                        type=discord.AutoModRuleActionType.timeout,
                        duration=timedelta(seconds=duration_seconds),
                    )
                )
        return result
