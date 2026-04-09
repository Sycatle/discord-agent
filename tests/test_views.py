import asyncio
from unittest.mock import MagicMock

import pytest

from architect.bot.views import ConfirmResult, ConfirmView


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


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
