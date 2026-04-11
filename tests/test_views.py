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


def test_plan_view_build_embed_with_many_actions(event_loop):
    actions = [{"type": "create_text_channel", "params": {"name": f"ch{i}"}} for i in range(35)]
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
