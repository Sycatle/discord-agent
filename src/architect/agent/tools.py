READONLY_TOOLS: frozenset[str] = frozenset({
    "list_channels", "list_roles",
    "get_member_roles", "get_server_info",
    "list_invites", "list_webhooks",
    "list_scheduled_events", "list_automod_rules",
})

META_TOOLS: frozenset[str] = frozenset({"ask_clarification", "generate_plan"})

MUTATION_TOOLS: frozenset[str] = frozenset({
    # existing
    "create_category", "create_text_channel", "create_voice_channel",
    "create_role", "set_channel_permissions",
    # domain 1
    "create_forum_channel", "create_stage_channel",
    "edit_channel", "delete_channel",
    "create_invite", "delete_invite",
    "create_webhook", "edit_webhook", "delete_webhook",
    # domain 2
    "edit_role", "delete_role", "assign_role", "remove_role",
    # domain 3
    "edit_member",
    # domain 4
    "create_scheduled_event", "edit_scheduled_event", "delete_scheduled_event",
    # domain 5
    "create_automod_rule", "edit_automod_rule", "delete_automod_rule",
    # domain 6
    "edit_server",
    # domain 7
    "edit_welcome_screen",
})

_ALL_ACTION_TYPES = sorted(MUTATION_TOOLS)  # sorted for deterministic order across restarts


def get_tools() -> list[dict]:
    return [
        # ── Existing ──────────────────────────────────────────────────────────
        {
            "name": "create_category",
            "description": "Crée une catégorie Discord dans le guild.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nom de la catégorie"},
                },
                "required": ["name"],
            },
        },
        {
            "name": "create_text_channel",
            "description": "Crée un channel texte, optionnellement dans une catégorie.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nom du channel"},
                    "category": {"type": "string", "description": "Nom de la catégorie parente (optionnel)"},
                },
                "required": ["name"],
            },
        },
        {
            "name": "create_voice_channel",
            "description": "Crée un channel vocal, optionnellement dans une catégorie.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nom du channel vocal"},
                    "category": {"type": "string", "description": "Nom de la catégorie parente (optionnel)"},
                },
                "required": ["name"],
            },
        },
        {
            "name": "create_role",
            "description": "Crée un rôle Discord.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nom du rôle"},
                    "color": {"type": "string", "description": "Couleur hex du rôle, ex: '#3498DB' (optionnel)"},
                    "mentionable": {"type": "boolean", "description": "Si le rôle est mentionnable (optionnel)"},
                },
                "required": ["name"],
            },
        },
        {
            "name": "set_channel_permissions",
            "description": "Définit les permissions d'un channel pour un rôle.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Nom du channel"},
                    "role": {"type": "string", "description": "Nom du rôle"},
                    "allow": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Liste des permissions à autoriser (optionnel)",
                    },
                    "deny": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Liste des permissions à refuser (optionnel)",
                    },
                },
                "required": ["channel", "role"],
            },
        },
        # ── Domain 1 — Channels ───────────────────────────────────────────────
        {
            "name": "create_forum_channel",
            "description": "Crée un channel forum Discord (threads avec tags).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nom du forum"},
                    "category": {"type": "string", "description": "Catégorie parente (optionnel)"},
                    "topic": {"type": "string", "description": "Description du forum, max 4096 chars (optionnel)"},
                    "slowmode": {"type": "integer", "description": "Délai entre messages en secondes, 0-21600 (optionnel)"},
                    "nsfw": {"type": "boolean", "description": "Contenu adulte (optionnel)"},
                    "available_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Noms des tags disponibles, max 20 (optionnel)",
                    },
                    "require_tag": {"type": "boolean", "description": "Obliger un tag sur chaque thread (optionnel)"},
                    "default_sort_order": {
                        "type": "string",
                        "enum": ["latest_activity", "creation_date"],
                        "description": "Ordre de tri des threads (optionnel)",
                    },
                    "default_forum_layout": {
                        "type": "string",
                        "enum": ["list", "gallery"],
                        "description": "Vue par défaut du forum (optionnel)",
                    },
                },
                "required": ["name"],
            },
        },
        {
            "name": "create_stage_channel",
            "description": "Crée un channel Stage (conférences/podcasts).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nom du stage"},
                    "category": {"type": "string", "description": "Catégorie parente (optionnel)"},
                    "bitrate": {"type": "integer", "description": "Qualité audio en bps (optionnel)"},
                    "user_limit": {"type": "integer", "description": "Limite d'utilisateurs 0-10000 (optionnel)"},
                    "rtc_region": {"type": "string", "description": "Région vocale override, null = auto (optionnel)"},
                    "position": {"type": "integer", "description": "Position dans la liste (optionnel)"},
                },
                "required": ["name"],
            },
        },
        {
            "name": "edit_channel",
            "description": "Modifie un channel ou une catégorie existant (renommer, topic, slowmode, nsfw, position, bitrate, etc.).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Nom ou ID du channel"},
                    "name": {"type": "string", "description": "Nouveau nom (optionnel)"},
                    "topic": {"type": "string", "description": "Topic du channel, max 1024 chars (optionnel)"},
                    "slowmode": {"type": "integer", "description": "Délai slowmode en secondes, 0-21600 (optionnel)"},
                    "nsfw": {"type": "boolean", "description": "Contenu adulte (optionnel)"},
                    "position": {"type": "integer", "description": "Position dans la liste (optionnel)"},
                    "bitrate": {"type": "integer", "description": "Qualité audio en bps, voice/stage uniquement (optionnel)"},
                    "user_limit": {"type": "integer", "description": "Limite membres, voice: 0-99 (optionnel)"},
                    "parent_id": {"type": "string", "description": "Déplacer vers cette catégorie (nom ou ID) (optionnel)"},
                    "rtc_region": {"type": "string", "description": "Région vocale override (optionnel)"},
                    "video_quality_mode": {
                        "type": "string",
                        "enum": ["auto", "full"],
                        "description": "Qualité vidéo voice/stage (optionnel)",
                    },
                    "default_auto_archive_duration": {
                        "type": "integer",
                        "enum": [60, 1440, 4320, 10080],
                        "description": "Durée d'archivage des threads en minutes (optionnel)",
                    },
                },
                "required": ["channel"],
            },
        },
        {
            "name": "delete_channel",
            "description": "Supprime définitivement un channel ou une catégorie. IRRÉVERSIBLE.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Nom ou ID du channel à supprimer"},
                    "reason": {"type": "string", "description": "Raison de la suppression (optionnel)"},
                },
                "required": ["channel"],
            },
        },
        {
            "name": "create_invite",
            "description": "Crée un lien d'invitation pour un channel.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Nom ou ID du channel"},
                    "max_age": {"type": "integer", "description": "Durée de validité en secondes, 0 = permanent, max 604800 (optionnel)"},
                    "max_uses": {"type": "integer", "description": "Nombre max d'utilisations, 0 = illimité, max 100 (optionnel)"},
                    "temporary": {"type": "boolean", "description": "Kicker si aucun rôle assigné (optionnel)"},
                },
                "required": ["channel"],
            },
        },
        {
            "name": "delete_invite",
            "description": "Révoque un lien d'invitation par son code.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code de l'invitation (ex: 'xKy3h2')"},
                },
                "required": ["code"],
            },
        },
        {
            "name": "create_webhook",
            "description": "Crée un webhook entrant sur un channel.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Nom ou ID du channel"},
                    "name": {"type": "string", "description": "Nom du webhook"},
                },
                "required": ["channel", "name"],
            },
        },
        {
            "name": "edit_webhook",
            "description": "Renomme un webhook ou le déplace vers un autre channel.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "webhook": {"type": "string", "description": "Nom ou ID du webhook"},
                    "name": {"type": "string", "description": "Nouveau nom (optionnel)"},
                    "channel": {"type": "string", "description": "Déplacer vers ce channel (nom ou ID) (optionnel)"},
                },
                "required": ["webhook"],
            },
        },
        {
            "name": "delete_webhook",
            "description": "Supprime un webhook.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "webhook": {"type": "string", "description": "Nom ou ID du webhook"},
                },
                "required": ["webhook"],
            },
        },
        # ── Domain 2 — Roles ──────────────────────────────────────────────────
        {
            "name": "edit_role",
            "description": "Modifie un rôle existant (nom, couleur, hoist, mentionnable). Interdit sur @everyone.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "description": "Nom ou ID du rôle"},
                    "name": {"type": "string", "description": "Nouveau nom (optionnel)"},
                    "color": {"type": "string", "description": "Couleur hex '#RRGGBB' (optionnel)"},
                    "hoist": {"type": "boolean", "description": "Afficher séparément dans la liste membres (optionnel)"},
                    "mentionable": {"type": "boolean", "description": "Permettre les @mentions (optionnel)"},
                },
                "required": ["role"],
            },
        },
        {
            "name": "delete_role",
            "description": "Supprime un rôle. IRRÉVERSIBLE. Interdit sur @everyone.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "description": "Nom ou ID du rôle"},
                    "reason": {"type": "string", "description": "Raison (optionnel)"},
                },
                "required": ["role"],
            },
        },
        {
            "name": "assign_role",
            "description": "Attribue un rôle à un membre (via @mention ou user_id).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "user": {"type": "string", "description": "@mention ou user_id numérique"},
                    "role": {"type": "string", "description": "Nom ou ID du rôle"},
                },
                "required": ["user", "role"],
            },
        },
        {
            "name": "remove_role",
            "description": "Retire un rôle d'un membre.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "user": {"type": "string", "description": "@mention ou user_id numérique"},
                    "role": {"type": "string", "description": "Nom ou ID du rôle"},
                },
                "required": ["user", "role"],
            },
        },
        # ── Domain 3 — Members ────────────────────────────────────────────────
        {
            "name": "edit_member",
            "description": "Modifie un membre : surnom, mute/sourd serveur, timeout, déplacer vers un vocal.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "user": {"type": "string", "description": "@mention ou user_id numérique"},
                    "nick": {"type": "string", "description": "Nouveau surnom, null pour reset (optionnel)"},
                    "mute": {"type": "boolean", "description": "Mute serveur en vocal (optionnel)"},
                    "deaf": {"type": "boolean", "description": "Sourd serveur en vocal (optionnel)"},
                    "timeout_until": {
                        "type": "string",
                        "description": "ISO8601 datetime UTC jusqu'où le timeout dure, null pour supprimer (optionnel)",
                    },
                    "move_to_channel": {
                        "type": "string",
                        "description": "Nom ou ID d'un channel vocal pour déplacer le membre (optionnel)",
                    },
                },
                "required": ["user"],
            },
        },
        # ── Domain 4 — Scheduled Events ───────────────────────────────────────
        {
            "name": "create_scheduled_event",
            "description": "Crée un événement planifié Discord (vocal, scène, ou externe).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Titre de l'événement"},
                    "start_time": {"type": "string", "description": "Début ISO8601 UTC, ex: '2026-05-01T18:00:00Z'"},
                    "entity_type": {
                        "type": "string",
                        "enum": ["voice", "stage", "external"],
                        "description": "Type : 'voice' (channel vocal), 'stage' (scène), 'external' (lieu physique)",
                    },
                    "channel": {
                        "type": "string",
                        "description": "Nom ou ID du channel vocal/scène (requis pour voice/stage)",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "Fin ISO8601 UTC (requis pour external, optionnel sinon)",
                    },
                    "location": {
                        "type": "string",
                        "description": "Lieu physique (requis pour external)",
                    },
                    "description": {"type": "string", "description": "Description de l'événement (optionnel)"},
                },
                "required": ["name", "start_time", "entity_type"],
            },
        },
        {
            "name": "edit_scheduled_event",
            "description": "Modifie un événement planifié ou change son statut.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "event": {"type": "string", "description": "Nom ou ID de l'événement"},
                    "name": {"type": "string", "description": "Nouveau titre (optionnel)"},
                    "start_time": {"type": "string", "description": "Nouvelle heure de début ISO8601 (optionnel)"},
                    "end_time": {"type": "string", "description": "Nouvelle heure de fin ISO8601 (optionnel)"},
                    "description": {"type": "string", "description": "Nouvelle description (optionnel)"},
                    "status": {
                        "type": "string",
                        "enum": ["active", "completed", "canceled"],
                        "description": "Transition de statut (optionnel)",
                    },
                },
                "required": ["event"],
            },
        },
        {
            "name": "delete_scheduled_event",
            "description": "Supprime un événement planifié.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "event": {"type": "string", "description": "Nom ou ID de l'événement"},
                },
                "required": ["event"],
            },
        },
        # ── Domain 5 — AutoMod ────────────────────────────────────────────────
        {
            "name": "create_automod_rule",
            "description": "Crée une règle AutoMod (filtre mots-clés, spam, mentions excessives).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nom de la règle"},
                    "event_type": {
                        "type": "string",
                        "enum": ["message_send", "member_update"],
                        "description": "Événement surveillé",
                    },
                    "trigger_type": {
                        "type": "string",
                        "enum": ["keyword", "spam", "keyword_preset", "mention_spam"],
                        "description": "Type de déclencheur",
                    },
                    "actions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Actions : 'block_message', 'send_alert:<channel>', 'timeout:<secondes>'",
                    },
                    "keyword_filter": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Mots-clés à bloquer pour trigger 'keyword' (optionnel)",
                    },
                    "regex_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Patterns regex Rust max 10 (optionnel)",
                    },
                    "allow_list": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Mots exemptés (optionnel)",
                    },
                    "presets": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["profanity", "sexual_content", "slurs"],
                        },
                        "description": "Presets prédéfinis pour trigger 'keyword_preset' (optionnel)",
                    },
                    "mention_limit": {
                        "type": "integer",
                        "description": "Nb max de mentions uniques pour trigger 'mention_spam' (1-50) (optionnel)",
                    },
                    "exempt_roles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Rôles exemptés (noms ou IDs), max 20 (optionnel)",
                    },
                    "exempt_channels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Channels exemptés (noms ou IDs), max 50 (optionnel)",
                    },
                    "enabled": {"type": "boolean", "description": "Activer la règle (défaut false) (optionnel)"},
                },
                "required": ["name", "event_type", "trigger_type", "actions"],
            },
        },
        {
            "name": "edit_automod_rule",
            "description": "Modifie une règle AutoMod existante.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "rule": {"type": "string", "description": "Nom ou ID de la règle"},
                    "name": {"type": "string", "description": "Nouveau nom (optionnel)"},
                    "enabled": {"type": "boolean", "description": "Activer/désactiver (optionnel)"},
                    "keyword_filter": {"type": "array", "items": {"type": "string"}, "description": "Nouveaux mots-clés (optionnel)"},
                    "regex_patterns": {"type": "array", "items": {"type": "string"}, "description": "Nouveaux regex (optionnel)"},
                    "allow_list": {"type": "array", "items": {"type": "string"}, "description": "Nouvelle liste blanche (optionnel)"},
                    "actions": {"type": "array", "items": {"type": "string"}, "description": "Nouvelles actions (optionnel)"},
                    "exempt_roles": {"type": "array", "items": {"type": "string"}, "description": "Rôles exemptés (optionnel)"},
                    "exempt_channels": {"type": "array", "items": {"type": "string"}, "description": "Channels exemptés (optionnel)"},
                },
                "required": ["rule"],
            },
        },
        {
            "name": "delete_automod_rule",
            "description": "Supprime une règle AutoMod.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "rule": {"type": "string", "description": "Nom ou ID de la règle"},
                },
                "required": ["rule"],
            },
        },
        # ── Domain 6 — Server Settings ────────────────────────────────────────
        {
            "name": "edit_server",
            "description": "Modifie les paramètres du serveur Discord (niveau vérification, filtres, channels système, locale, etc.).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nouveau nom du serveur (optionnel)"},
                    "verification_level": {
                        "type": "string",
                        "enum": ["none", "low", "medium", "high", "highest"],
                        "description": "Niveau de vérification des nouveaux membres (optionnel)",
                    },
                    "default_message_notifications": {
                        "type": "string",
                        "enum": ["all_messages", "only_mentions"],
                        "description": "Notifications par défaut pour les nouveaux membres (optionnel)",
                    },
                    "explicit_content_filter": {
                        "type": "string",
                        "enum": ["disabled", "members_without_roles", "all_members"],
                        "description": "Niveau de filtrage du contenu explicite (optionnel)",
                    },
                    "afk_channel": {
                        "type": "string",
                        "description": "Nom ou ID du channel vocal AFK, null pour désactiver (optionnel)",
                    },
                    "afk_timeout": {
                        "type": "integer",
                        "enum": [60, 300, 900, 1800, 3600],
                        "description": "Délai AFK en secondes (optionnel)",
                    },
                    "system_channel": {
                        "type": "string",
                        "description": "Nom ou ID du channel pour messages système (accueil, boosts) (optionnel)",
                    },
                    "rules_channel": {
                        "type": "string",
                        "description": "Nom ou ID du channel rules (serveurs communauté) (optionnel)",
                    },
                    "public_updates_channel": {
                        "type": "string",
                        "description": "Nom ou ID du channel mises à jour Discord (serveurs communauté) (optionnel)",
                    },
                    "safety_alerts_channel": {
                        "type": "string",
                        "description": "Nom ou ID du channel alertes sécurité Discord (optionnel)",
                    },
                    "description": {"type": "string", "description": "Description du serveur communauté (optionnel)"},
                    "preferred_locale": {
                        "type": "string",
                        "description": "Langue préférée ex: 'fr', 'en-US', 'de' (optionnel)",
                    },
                    "premium_progress_bar_enabled": {
                        "type": "boolean",
                        "description": "Afficher la barre de progression des boosts (optionnel)",
                    },
                },
            },
        },
        # ── Domain 7 — Welcome Screen ─────────────────────────────────────────
        {
            "name": "edit_welcome_screen",
            "description": "Modifie l'écran de bienvenue du serveur communauté.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean", "description": "Activer l'écran de bienvenue (optionnel)"},
                    "description": {"type": "string", "description": "Texte d'accueil affiché (optionnel)"},
                    "welcome_channels": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "channel": {"type": "string", "description": "Nom ou ID du channel"},
                                "description": {"type": "string", "description": "Courte description"},
                                "emoji": {"type": "string", "description": "Emoji Unicode (optionnel)"},
                            },
                            "required": ["channel", "description"],
                        },
                        "description": "Channels mis en avant, max 5 (optionnel)",
                    },
                },
            },
        },
        # ── Read-only ─────────────────────────────────────────────────────────
        {
            "name": "list_channels",
            "description": "Liste les channels et catégories du guild.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "list_roles",
            "description": "Liste les rôles du guild.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "get_member_roles",
            "description": "Liste les rôles actuels d'un membre.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "user": {"type": "string", "description": "@mention ou user_id numérique"},
                },
                "required": ["user"],
            },
        },
        {
            "name": "get_server_info",
            "description": "Retourne les paramètres actuels du serveur (niveau vérification, filtres, locale, boost, etc.).",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "list_invites",
            "description": "Liste les invitations actives du serveur.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "list_webhooks",
            "description": "Liste les webhooks du serveur.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "list_scheduled_events",
            "description": "Liste les événements planifiés du serveur.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "list_automod_rules",
            "description": "Liste les règles AutoMod du serveur.",
            "input_schema": {"type": "object", "properties": {}},
        },
        # ── Meta ──────────────────────────────────────────────────────────────
        {
            "name": "ask_clarification",
            "description": "Pose une question à l'utilisateur pour clarifier sa demande avant d'agir.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "La question à poser à l'utilisateur"},
                },
                "required": ["question"],
            },
        },
        {
            "name": "generate_plan",
            "description": "Génère un plan complet de configuration Discord. Utilise ce tool quand la demande implique de créer ou modifier plusieurs éléments en une seule opération. Le plan sera présenté à l'utilisateur pour validation avant toute exécution.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Titre du plan (ex: 'Serveur Gaming Pro')"},
                    "actions": {
                        "type": "array",
                        "description": "Liste ordonnée des actions à exécuter",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": _ALL_ACTION_TYPES,
                                    "description": "Type d'action",
                                },
                                "params": {"type": "object", "description": "Paramètres de l'action"},
                            },
                            "required": ["type", "params"],
                        },
                    },
                },
                "required": ["title", "actions"],
            },
        },
    ]
