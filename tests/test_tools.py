from architect.agent.tools import READONLY_TOOLS, META_TOOLS, get_tools

MUTATION_TOOLS = {"create_category", "create_text_channel", "create_voice_channel", "create_role", "set_channel_permissions"}


def test_get_tools_returns_nonempty_list():
    tools = get_tools()
    assert isinstance(tools, list)
    assert len(tools) > 0


def test_each_tool_has_required_keys():
    for tool in get_tools():
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool


def test_readonly_tools_contents():
    assert "list_channels" in READONLY_TOOLS
    assert "list_roles" in READONLY_TOOLS


def test_meta_tools_contents():
    assert "ask_clarification" in META_TOOLS


def test_mutation_tools_not_in_readonly_or_meta():
    tool_names = {t["name"] for t in get_tools()}
    for name in MUTATION_TOOLS:
        assert name in tool_names, f"{name} absent de get_tools()"
        assert name not in READONLY_TOOLS, f"{name} ne doit pas être dans READONLY_TOOLS"
        assert name not in META_TOOLS, f"{name} ne doit pas être dans META_TOOLS"
