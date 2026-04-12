from architect.agent.tools import READONLY_TOOLS, META_TOOLS, MUTATION_TOOLS, get_tools

ALL_MUTATION_TOOLS = {
    # existing
    "create_category", "create_text_channel", "create_voice_channel",
    "create_role", "set_channel_permissions",
    # domain 1
    "create_forum_channel", "create_stage_channel", "edit_channel", "delete_channel",
    "create_invite", "delete_invite", "create_webhook", "edit_webhook", "delete_webhook",
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
}

ALL_READONLY_TOOLS = {
    "list_channels", "list_roles",
    "get_member_roles", "get_server_info",
    "list_invites", "list_webhooks",
    "list_scheduled_events", "list_automod_rules",
}


def test_get_tools_returns_nonempty_list():
    tools = get_tools()
    assert isinstance(tools, list)
    assert len(tools) > 0


def test_each_tool_has_required_keys():
    for tool in get_tools():
        assert "name" in tool, f"{tool} missing 'name'"
        assert "description" in tool, f"{tool} missing 'description'"
        assert "input_schema" in tool, f"{tool} missing 'input_schema'"


def test_readonly_tools_contents():
    for name in ALL_READONLY_TOOLS:
        assert name in READONLY_TOOLS, f"{name} absent de READONLY_TOOLS"


def test_meta_tools_contents():
    assert "ask_clarification" in META_TOOLS
    assert "generate_plan" in META_TOOLS


def test_mutation_tools_not_in_readonly_or_meta():
    tool_names = {t["name"] for t in get_tools()}
    for name in ALL_MUTATION_TOOLS:
        assert name in tool_names, f"{name} absent de get_tools()"
        assert name not in READONLY_TOOLS, f"{name} ne doit pas être dans READONLY_TOOLS"
        assert name not in META_TOOLS, f"{name} ne doit pas être dans META_TOOLS"


def test_mutation_tools_frozenset_complete():
    for name in ALL_MUTATION_TOOLS:
        assert name in MUTATION_TOOLS, f"{name} absent du frozenset MUTATION_TOOLS"


def test_edit_channel_schema():
    tools = {t["name"]: t for t in get_tools()}
    schema = tools["edit_channel"]["input_schema"]
    assert "channel" in schema["properties"]
    assert "channel" in schema["required"]
    for opt in ["name", "topic", "slowmode", "nsfw", "bitrate", "user_limit"]:
        assert opt in schema["properties"], f"edit_channel missing optional param: {opt}"


def test_assign_role_schema():
    tools = {t["name"]: t for t in get_tools()}
    schema = tools["assign_role"]["input_schema"]
    assert "user" in schema["required"]
    assert "role" in schema["required"]


def test_create_automod_rule_schema():
    tools = {t["name"]: t for t in get_tools()}
    schema = tools["create_automod_rule"]["input_schema"]
    for req in ["name", "event_type", "trigger_type", "actions"]:
        assert req in schema["required"], f"create_automod_rule missing required: {req}"


def test_create_scheduled_event_schema():
    tools = {t["name"]: t for t in get_tools()}
    schema = tools["create_scheduled_event"]["input_schema"]
    for req in ["name", "start_time", "entity_type"]:
        assert req in schema["required"], f"create_scheduled_event missing required: {req}"


def test_generate_plan_enum_includes_new_types():
    tools = {t["name"]: t for t in get_tools()}
    enum_values = tools["generate_plan"]["input_schema"]["properties"]["actions"]["items"]["properties"]["type"]["enum"]
    for name in ["edit_channel", "delete_channel", "edit_role", "assign_role", "edit_server"]:
        assert name in enum_values, f"generate_plan enum missing: {name}"
