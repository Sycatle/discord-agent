READONLY_TOOLS: frozenset[str] = frozenset({"list_channels", "list_roles"})

META_TOOLS: frozenset[str] = frozenset({"ask_clarification", "generate_plan"})

MUTATION_TOOLS: frozenset[str] = frozenset({
    "create_category",
    "create_text_channel",
    "create_voice_channel",
    "create_role",
    "set_channel_permissions",
})


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
        {
            "name": "generate_plan",
            "description": "Génère un plan complet de configuration Discord. Utilise ce tool quand la demande implique de créer plusieurs éléments (catégories, channels, rôles) en une seule opération. Le plan sera présenté à l'utilisateur pour validation avant toute exécution.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Titre du plan (ex: 'Serveur Gaming Pro')",
                    },
                    "actions": {
                        "type": "array",
                        "description": "Liste ordonnée des actions à exécuter",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": [
                                        "create_category",
                                        "create_text_channel",
                                        "create_voice_channel",
                                        "create_role",
                                        "set_channel_permissions",
                                    ],
                                    "description": "Type d'action",
                                },
                                "params": {
                                    "type": "object",
                                    "description": "Paramètres de l'action",
                                },
                            },
                            "required": ["type", "params"],
                        },
                    },
                },
                "required": ["title", "actions"],
            },
        },
    ]
