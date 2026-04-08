# tests/test_models.py
import pytest
from pydantic import ValidationError
from architect.models.actions import Action, ActionType
from architect.models.plan import Plan


def test_action_type_whitelist_rejects_unknown():
    with pytest.raises(ValidationError):
        Action(type="delete_channel", params={})


def test_action_type_accepts_all_valid():
    for t in ActionType:
        a = Action(type=t, params={"name": "test"})
        assert a.type == t


def test_plan_rejects_extra_fields():
    with pytest.raises(ValidationError):
        Plan(
            title="T",
            description="D",
            actions=[],
            unexpected_field="oops",
        )


def test_plan_valid_roundtrip():
    raw = '{"title":"T","description":"D","actions":[{"type":"create_category","params":{"name":"Gaming"}}]}'
    plan = Plan.model_validate_json(raw)
    assert plan.title == "T"
    assert plan.actions[0].type == ActionType.CREATE_CATEGORY
    assert plan.actions[0].params == {"name": "Gaming"}


def test_plan_rejects_unknown_action_type_in_json():
    raw = '{"title":"T","description":"D","actions":[{"type":"nuke_server","params":{}}]}'
    with pytest.raises(ValidationError):
        Plan.model_validate_json(raw)
