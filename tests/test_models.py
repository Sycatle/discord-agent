import pytest
from pydantic import ValidationError

from architect.models.actions import Action, ActionType


def test_action_type_whitelist_rejects_unknown():
    with pytest.raises(ValidationError):
        Action(type="nuke_server", params={})


def test_action_type_accepts_all_valid():
    assert len(ActionType) == 27  # 5 existing + 22 new; catches silent StrEnum value aliasing
    for t in ActionType:
        a = Action(type=t, params={"name": "test"})
        assert a.type == t


def test_new_channel_action_types():
    for t in [
        ActionType.CREATE_FORUM_CHANNEL,
        ActionType.CREATE_STAGE_CHANNEL,
        ActionType.EDIT_CHANNEL,
        ActionType.DELETE_CHANNEL,
        ActionType.CREATE_INVITE,
        ActionType.DELETE_INVITE,
        ActionType.CREATE_WEBHOOK,
        ActionType.EDIT_WEBHOOK,
        ActionType.DELETE_WEBHOOK,
    ]:
        a = Action(type=t, params={})
        assert a.type == t


def test_new_role_action_types():
    for t in [
        ActionType.EDIT_ROLE,
        ActionType.DELETE_ROLE,
        ActionType.ASSIGN_ROLE,
        ActionType.REMOVE_ROLE,
    ]:
        a = Action(type=t, params={})
        assert a.type == t


def test_new_member_action_types():
    a = Action(type=ActionType.EDIT_MEMBER, params={})
    assert a.type == ActionType.EDIT_MEMBER


def test_new_event_action_types():
    for t in [
        ActionType.CREATE_SCHEDULED_EVENT,
        ActionType.EDIT_SCHEDULED_EVENT,
        ActionType.DELETE_SCHEDULED_EVENT,
    ]:
        a = Action(type=t, params={})
        assert a.type == t


def test_new_automod_action_types():
    for t in [
        ActionType.CREATE_AUTOMOD_RULE,
        ActionType.EDIT_AUTOMOD_RULE,
        ActionType.DELETE_AUTOMOD_RULE,
    ]:
        a = Action(type=t, params={})
        assert a.type == t


def test_new_server_action_types():
    for t in [ActionType.EDIT_SERVER, ActionType.EDIT_WELCOME_SCREEN]:
        a = Action(type=t, params={})
        assert a.type == t
