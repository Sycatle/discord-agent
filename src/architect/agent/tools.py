READONLY_TOOLS: frozenset[str] = frozenset({"list_channels", "list_roles"})

META_TOOLS: frozenset[str] = frozenset({"ask_clarification"})


def get_tools() -> list[dict]:
    return [
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
                    "category": {
                        "type": "string",
                        "description": "Nom de la catégorie parente (optionnel)",
                    },
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
                    "category": {
                        "type": "string",
                        "description": "Nom de la catégorie parente (optionnel)",
                    },
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
                    "color": {
                        "type": "string",
                        "description": "Couleur hex du rôle, ex: '#3498DB' (optionnel)",
                    },
                    "mentionable": {
                        "type": "boolean",
                        "description": "Si le rôle est mentionnable (optionnel)",
                    },
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
        {
            "name": "list_channels",
            "description": "Liste les channels et catégories du guild.",
            "input_schema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "list_roles",
            "description": "Liste les rôles du guild.",
            "input_schema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "ask_clarification",
            "description": "Pose une question à l'utilisateur pour clarifier sa demande avant d'agir.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "La question à poser à l'utilisateur",
                    },
                },
                "required": ["question"],
            },
        },
    ]
