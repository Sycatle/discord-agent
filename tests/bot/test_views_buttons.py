"""Coverage for view button callbacks (ConfirmView / PlanView / PlanReviewView).

The discord.py ``@discord.ui.button`` decorator wraps the async method as
a UI callback. We invoke the callbacks directly with mock interactions —
that's the same code path the dispatcher would hit when a real user clicks.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from architect.bot.views import (
    ConfirmResult,
    ConfirmView,
    PlanResult,
    PlanReviewResult,
    PlanReviewView,
    PlanView,
)


def _interaction(user_id: int) -> MagicMock:
    interaction = MagicMock()
    interaction.user.id = user_id
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    return interaction


# ── ConfirmView ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_confirm_view_confirm_sets_future():
    view = ConfirmView(invoker_id=1)
    interaction = _interaction(user_id=1)
    await view.confirm.callback(interaction)
    assert view._future is not None
    assert view._future.result() == ConfirmResult.CONFIRMED


@pytest.mark.asyncio
async def test_confirm_view_cancel_sets_future():
    view = ConfirmView(invoker_id=1)
    interaction = _interaction(user_id=1)
    await view.cancel.callback(interaction)
    assert view._future.result() == ConfirmResult.CANCELLED


@pytest.mark.asyncio
async def test_confirm_view_cancel_all_sets_future():
    view = ConfirmView(invoker_id=1)
    interaction = _interaction(user_id=1)
    await view.cancel_all.callback(interaction)
    assert view._future.result() == ConfirmResult.CANCELLED_ALL


@pytest.mark.asyncio
@pytest.mark.parametrize("button_name", ["confirm", "cancel", "cancel_all"])
async def test_confirm_view_non_invoker_rejected(button_name):
    view = ConfirmView(invoker_id=1)
    interaction = _interaction(user_id=999)
    button = getattr(view, button_name)
    await button.callback(interaction)
    interaction.response.send_message.assert_called_once()
    assert "author" in interaction.response.send_message.call_args.args[0].lower()
    # No future should be resolved
    assert view._future is None


@pytest.mark.asyncio
async def test_confirm_view_wait_result_timeout_returns_cancelled():
    view = ConfirmView(invoker_id=1)
    # Skip the actual wait
    view.wait = AsyncMock(return_value=None)
    result = await view.wait_result()
    assert result == ConfirmResult.CANCELLED


# ── PlanView ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_plan_view_confirm_all():
    view = PlanView(title="t", actions=[], invoker_id=1)
    await view.confirm_all.callback(_interaction(user_id=1))
    assert view._future.result() == PlanResult.CONFIRMED_ALL


@pytest.mark.asyncio
async def test_plan_view_confirm_atomic():
    view = PlanView(title="t", actions=[], invoker_id=1)
    await view.confirm_atomic.callback(_interaction(user_id=1))
    assert view._future.result() == PlanResult.CONFIRMED_ATOMIC


@pytest.mark.asyncio
async def test_plan_view_review():
    view = PlanView(title="t", actions=[], invoker_id=1)
    await view.review.callback(_interaction(user_id=1))
    assert view._future.result() == PlanResult.REVIEW


@pytest.mark.asyncio
async def test_plan_view_cancel():
    view = PlanView(title="t", actions=[], invoker_id=1)
    await view.cancel.callback(_interaction(user_id=1))
    assert view._future.result() == PlanResult.CANCELLED


@pytest.mark.asyncio
@pytest.mark.parametrize("button_name", ["confirm_all", "confirm_atomic", "review", "cancel"])
async def test_plan_view_non_invoker_rejected(button_name):
    view = PlanView(title="t", actions=[], invoker_id=1)
    interaction = _interaction(user_id=2)
    button = getattr(view, button_name)
    await button.callback(interaction)
    interaction.response.send_message.assert_called_once()
    assert view._future is None


@pytest.mark.asyncio
async def test_plan_view_wait_result_timeout_returns_cancelled():
    view = PlanView(title="t", actions=[], invoker_id=1)
    view.wait = AsyncMock(return_value=None)
    assert await view.wait_result() == PlanResult.CANCELLED


def test_plan_view_summary_with_unknown_action_type_shows_other():
    """An action whose type is outside the three domain buckets should land
    in the 'other' bucket of the embed summary."""
    actions = [{"type": "definitely_not_a_real_type", "params": {}}]
    view = PlanView(title="t", actions=actions, invoker_id=1)
    embed, _ = view.build_embed()
    assert "other" in (embed.description or "").lower()


def test_plan_view_summary_no_actions():
    view = PlanView(title="t", actions=[], invoker_id=1)
    embed, _ = view.build_embed()
    assert "No actions" in (embed.description or "")


# ── PlanReviewView ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_plan_review_view_confirm_one():
    view = PlanReviewView(invoker_id=1)
    await view.confirm.callback(_interaction(user_id=1))
    assert view._future.result() == PlanReviewResult.CONFIRMED


@pytest.mark.asyncio
async def test_plan_review_view_skip_one():
    view = PlanReviewView(invoker_id=1)
    await view.skip.callback(_interaction(user_id=1))
    assert view._future.result() == PlanReviewResult.SKIPPED


@pytest.mark.asyncio
async def test_plan_review_view_auto_rest():
    view = PlanReviewView(invoker_id=1)
    await view.auto_rest.callback(_interaction(user_id=1))
    assert view._future.result() == PlanReviewResult.AUTO_REST


@pytest.mark.asyncio
async def test_plan_review_view_cancel_all():
    view = PlanReviewView(invoker_id=1)
    await view.cancel_all.callback(_interaction(user_id=1))
    assert view._future.result() == PlanReviewResult.CANCELLED_ALL


@pytest.mark.asyncio
@pytest.mark.parametrize("button_name", ["confirm", "skip", "auto_rest", "cancel_all"])
async def test_plan_review_view_non_invoker_rejected(button_name):
    view = PlanReviewView(invoker_id=1)
    interaction = _interaction(user_id=2)
    button = getattr(view, button_name)
    await button.callback(interaction)
    interaction.response.send_message.assert_called_once()
    assert view._future is None
