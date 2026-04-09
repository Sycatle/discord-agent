import pytest
from pydantic import ValidationError
from architect.models.actions import Action, ActionType


def test_action_type_whitelist_rejects_unknown():
    with pytest.raises(ValidationError):
        Action(type="delete_channel", params={})


def test_action_type_accepts_all_valid():
    for t in ActionType:
        a = Action(type=t, params={"name": "test"})
        assert a.type == t
