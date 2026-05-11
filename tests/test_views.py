import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from architect.bot.views import ConfirmResult, ConfirmView, PlanView


def test_confirm_result_enum_values():
    assert ConfirmResult.CONFIRMED.value == "confirmed"
    assert ConfirmResult.CANCELLED.value == "cancelled"
    assert ConfirmResult.CANCELLED_ALL.value == "cancelled_all"


def test_confirm_result_has_three_members():
    assert len(ConfirmResult) == 3


def test_confirm_view_instantiation(event_loop):
    view = ConfirmView(invoker_id=12345)
    assert view.invoker_id == 12345


def test_confirm_view_future_starts_none(event_loop):
    view = ConfirmView(invoker_id=12345)
    assert view._future is None  # lazy init — created on first async call


def test_is_invoker_true(event_loop):
    view = ConfirmView(invoker_id=12345)
    interaction = MagicMock()
    interaction.user.id = 12345
    assert view._is_invoker(interaction) is True


def test_is_invoker_false(event_loop):
    view = ConfirmView(invoker_id=12345)
    interaction = MagicMock()
    interaction.user.id = 99999
    assert view._is_invoker(interaction) is False


def test_plan_view_build_embed_summary(event_loop):
    actions = [
        {"type": "create_category", "params": {"name": "A"}},
        {"type": "create_text_channel", "params": {"name": "general"}},
        {"type": "create_role", "params": {"name": "Admin"}},
    ]
    view = PlanView(title="My Server", actions=actions, invoker_id=1)
    embed, file_content = view.build_embed()
    assert isinstance(embed, discord.Embed)
    assert "My Server" in embed.title
    assert file_content is None  # only 3 actions, no file needed


def test_plan_view_diff_groups_actions_by_category(event_loop):
    from architect.models.snapshot import ChannelInfo, GuildSnapshot

    snapshot = GuildSnapshot(
        categories=[ChannelInfo(id=10, name="Communauté", type="category", position=0)],
        channels=[
            ChannelInfo(id=20, name="general", type="text", parent_id=10, position=0)
        ],
    )
    actions = [
        {
            "type": "create_text_channel",
            "params": {"name": "annonces", "category": "Communauté"},
        },
        {
            "type": "edit_channel",
            "params": {"channel": "general", "name": "discussion"},
        },
    ]
    view = PlanView(
        title="Refonte", actions=actions, invoker_id=1, snapshot=snapshot
    )
    embed, _ = view.build_embed()
    diff_field = next(f for f in embed.fields if f.name == "Diff")
    assert "Communauté" in diff_field.value
    assert "+ `#annonces`" in diff_field.value
    assert "~ `#general`" in diff_field.value
    assert "→ `discussion`" in diff_field.value


def test_plan_view_warnings_field_shows_issues(event_loop):
    from architect.executor.validator import PlanIssue

    actions = [{"type": "create_text_channel", "params": {"name": "tmp"}}]
    issues = [PlanIssue(severity="warning", action_index=0, message="dupe risk")]
    view = PlanView(
        title="x", actions=actions, invoker_id=1, issues=issues
    )
    embed, _ = view.build_embed()
    warning_field = next(f for f in embed.fields if f.name == "Warnings")
    assert "dupe risk" in warning_field.value
    assert "⚠" in warning_field.value


def test_plan_view_error_issue_renders_with_cross(event_loop):
    from architect.executor.validator import PlanIssue

    issues = [PlanIssue(severity="error", action_index=0, message="ghost target")]
    view = PlanView(
        title="x",
        actions=[{"type": "edit_channel", "params": {"channel": "ghost"}}],
        invoker_id=1,
        issues=issues,
    )
    embed, _ = view.build_embed()
    warning_field = next(f for f in embed.fields if f.name == "Warnings")
    assert "❌" in warning_field.value
    assert "ghost" in warning_field.value


def test_undo_view_disables_button_after_click(event_loop):
    from architect.bot.views import UndoView

    inverse = [{"type": "delete_channel", "params": {"channel": "x"}}]
    view = UndoView(invoker_id=1, inverse_actions=inverse)
    assert view.inverse_actions == inverse
    assert view.timeout == 600


def test_plan_view_build_embed_with_many_actions(event_loop):
    # Long names + many actions push the rendered diff past the embed budget,
    # forcing the fallback `.txt` attachment.
    actions = [
        {
            "type": "create_text_channel",
            "params": {
                "name": f"a-very-long-channel-name-number-{i:03d}-with-extra-padding",
                "category": f"category-with-a-pretty-long-name-{i % 5}",
            },
        }
        for i in range(120)
    ]
    view = PlanView(title="Big Server", actions=actions, invoker_id=1)
    embed, file_content = view.build_embed()
    assert file_content is not None
    assert "Big Server" in file_content


@pytest.mark.asyncio
async def test_plan_review_view_timeout_returns_cancelled_all():
    from architect.bot.views import PlanReviewResult, PlanReviewView

    view = PlanReviewView(invoker_id=1)

    with patch.object(view, "wait", new_callable=AsyncMock) as mock_wait:
        mock_wait.return_value = None
        result = await view.wait_result()

    assert result == PlanReviewResult.CANCELLED_ALL


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Plan editing — Select removes an action and re-renders the embed
# ---------------------------------------------------------------------------


def test_plan_view_has_select_for_action_removal(event_loop):
    """The Select must be the first non-button child of the view."""
    from architect.bot.views import _PlanActionSelect

    actions = [
        {"type": "create_text_channel", "params": {"name": "general"}},
        {"type": "create_role", "params": {"name": "Modo"}},
    ]
    view = PlanView(title="t", actions=actions, invoker_id=1)
    selects = [c for c in view.children if isinstance(c, _PlanActionSelect)]
    assert len(selects) == 1
    assert len(selects[0].options) == 2
    # Options are formatted as "#N type: name".
    labels = [o.label for o in selects[0].options]
    assert labels[0].startswith("#1 ")
    assert "general" in labels[0]


def test_plan_view_select_truncates_above_25_actions(event_loop):
    actions = [
        {"type": "create_text_channel", "params": {"name": f"ch{i}"}}
        for i in range(40)
    ]
    view = PlanView(title="big", actions=actions, invoker_id=1)
    from architect.bot.views import _PlanActionSelect

    select = next(c for c in view.children if isinstance(c, _PlanActionSelect))
    assert len(select.options) == 25


@pytest.mark.asyncio
async def test_plan_view_rewire_select_after_removal():
    """After dropping an action, the Select must renumber from #1."""
    actions = [
        {"type": "create_text_channel", "params": {"name": "a"}},
        {"type": "create_text_channel", "params": {"name": "b"}},
        {"type": "create_text_channel", "params": {"name": "c"}},
    ]
    view = PlanView(title="t", actions=actions, invoker_id=1)
    del view.actions[1]  # remove "b"
    view._rewire_select()
    from architect.bot.views import _PlanActionSelect

    select = next(c for c in view.children if isinstance(c, _PlanActionSelect))
    labels = [o.label for o in select.options]
    assert len(labels) == 2
    assert labels[0].startswith("#1 ")
    assert "a" in labels[0]
    assert labels[1].startswith("#2 ")
    assert "c" in labels[1]


@pytest.mark.asyncio
async def test_plan_view_empty_disables_confirm_buttons():
    view = PlanView(title="t", actions=[], invoker_id=1)
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    # Cancel must stay enabled; the 3 confirm-style buttons must be disabled.
    by_label = {(b.label or "").lower(): b for b in buttons}
    assert by_label["confirm all"].disabled is True
    assert by_label["review"].disabled is True
    assert by_label["cancel"].disabled is False


@pytest.mark.asyncio
async def test_plan_view_select_callback_removes_action():
    """Simulate the user picking '#2' in the Select."""
    actions = [
        {"type": "create_text_channel", "params": {"name": "a"}},
        {"type": "create_role", "params": {"name": "Modo"}},
        {"type": "create_text_channel", "params": {"name": "c"}},
    ]
    view = PlanView(title="t", actions=actions, invoker_id=42)

    interaction = MagicMock()
    interaction.user.id = 42
    interaction.response.edit_message = AsyncMock()
    interaction.response.send_message = AsyncMock()

    select = view._select
    select._values = ["1"]  # discord.py stores chosen value in _values
    await select.callback(interaction)

    # Action #2 ("Modo") removed; 2 actions remain.
    assert len(view.actions) == 2
    assert all(a["params"].get("name") != "Modo" for a in view.actions)
    interaction.response.edit_message.assert_awaited_once()
