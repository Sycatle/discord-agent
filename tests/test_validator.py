"""Static plan validation."""

from __future__ import annotations

from architect.executor.validator import PlanIssue, validate_plan
from architect.models.snapshot import (
    AutoModRuleInfo,
    ChannelInfo,
    GuildSnapshot,
    RoleInfo,
)


def _snap(**overrides) -> GuildSnapshot:
    base: dict = {
        "categories": [],
        "channels": [],
        "roles": [],
        "automod_rules": [],
    }
    base.update(overrides)
    return GuildSnapshot(**base)


def test_empty_plan_warns():
    issues = validate_plan([], _snap())
    assert len(issues) == 1
    assert issues[0].severity == "warning"
    assert "Empty" in issues[0].message


def test_duplicate_create_in_plan_is_error():
    actions = [
        {"type": "create_text_channel", "params": {"name": "general"}},
        {"type": "create_text_channel", "params": {"name": "general"}},
    ]
    issues = validate_plan(actions, _snap())
    errors = [i for i in issues if i.severity == "error"]
    assert any("twice" in e.message for e in errors)


def test_create_when_exists_is_warning():
    snap = _snap(
        channels=[ChannelInfo(id=1, name="general", type="text", position=0)]
    )
    issues = validate_plan(
        [{"type": "create_text_channel", "params": {"name": "general"}}], snap
    )
    assert any(i.severity == "warning" and "edit_channel" in i.message for i in issues)


def test_edit_unknown_channel_is_error():
    issues = validate_plan(
        [{"type": "edit_channel", "params": {"channel": "ghost", "name": "new"}}],
        _snap(),
    )
    assert any(i.severity == "error" and "ghost" in i.message for i in issues)


def test_edit_channel_id_is_accepted_without_lookup():
    """A numeric ref is assumed to be a valid channel ID — we don't check."""
    issues = validate_plan(
        [{"type": "edit_channel", "params": {"channel": "123456789", "name": "n"}}],
        _snap(),
    )
    assert not any(i.severity == "error" for i in issues)


def test_create_then_delete_same_name_is_warning():
    actions = [
        {"type": "create_text_channel", "params": {"name": "tmp"}},
        {"type": "delete_channel", "params": {"channel": "tmp"}},
    ]
    issues = validate_plan(actions, _snap())
    assert any("churn" in i.message for i in issues)


def test_child_under_missing_category_is_error():
    issues = validate_plan(
        [
            {
                "type": "create_text_channel",
                "params": {"name": "ch", "category": "Ghost"},
            }
        ],
        _snap(),
    )
    assert any(i.severity == "error" and "Ghost" in i.message for i in issues)


def test_child_under_in_plan_category_is_ok():
    actions = [
        {"type": "create_category", "params": {"name": "New"}},
        {"type": "create_text_channel", "params": {"name": "ch", "category": "New"}},
    ]
    issues = validate_plan(actions, _snap())
    assert not any(i.severity == "error" for i in issues)


def test_automod_singleton_overflow_is_warning():
    snap = _snap(
        automod_rules=[AutoModRuleInfo(id=1, name="Anti-spam", trigger_type="spam")]
    )
    issues = validate_plan(
        [
            {
                "type": "create_automod_rule",
                "params": {
                    "name": "Anti-spam 2",
                    "trigger_type": "spam",
                    "event_type": "message_send",
                    "actions": ["block_message"],
                },
            }
        ],
        snap,
    )
    assert any(i.severity == "warning" and "trigger" in i.message for i in issues)


def test_delete_unknown_role_is_error():
    issues = validate_plan(
        [{"type": "delete_role", "params": {"role": "Nope"}}],
        _snap(roles=[RoleInfo(id=1, name="Modo", position=1)]),
    )
    assert any(i.severity == "error" and "Nope" in i.message for i in issues)


def test_plan_issue_is_error_property():
    err = PlanIssue(severity="error", action_index=0, message="x")
    warn = PlanIssue(severity="warning", action_index=0, message="x")
    assert err.is_error is True
    assert warn.is_error is False


def test_validator_returns_issues_in_action_order():
    actions = [
        {"type": "edit_channel", "params": {"channel": "ghost", "name": "n"}},
        {"type": "edit_role", "params": {"role": "alsoghost", "name": "x"}},
    ]
    issues = validate_plan(actions, _snap())
    indexes = [i.action_index for i in issues if i.severity == "error"]
    assert indexes == sorted(indexes)


def test_missing_required_field_is_error():
    issues = validate_plan(
        [{"type": "create_text_channel", "params": {}}], _snap()
    )
    assert any(i.severity == "error" and "name" in i.message for i in issues)
