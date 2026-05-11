"""Topological layering."""

from __future__ import annotations

from architect.executor.scheduler import build_layers


def test_empty_plan_returns_empty_layers():
    assert build_layers([]) == []


def test_independent_actions_share_one_layer():
    actions = [
        {"type": "create_role", "params": {"name": "A"}},
        {"type": "create_role", "params": {"name": "B"}},
        {"type": "create_role", "params": {"name": "C"}},
    ]
    layers = build_layers(actions)
    assert layers == [[0, 1, 2]]


def test_category_then_channels_form_two_layers():
    actions = [
        {"type": "create_category", "params": {"name": "Cat"}},
        {"type": "create_text_channel", "params": {"name": "ch1", "category": "Cat"}},
        {"type": "create_text_channel", "params": {"name": "ch2", "category": "Cat"}},
    ]
    layers = build_layers(actions)
    assert layers == [[0], [1, 2]]


def test_role_then_assign_serialise():
    actions = [
        {"type": "create_role", "params": {"name": "Modo"}},
        {"type": "assign_role", "params": {"role": "Modo", "user": "<@1>"}},
    ]
    assert build_layers(actions) == [[0], [1]]


def test_delete_then_create_same_name_is_two_layers():
    actions = [
        {"type": "delete_channel", "params": {"channel": "old"}},
        {"type": "create_text_channel", "params": {"name": "old"}},
    ]
    layers = build_layers(actions)
    assert layers == [[0], [1]]


def test_two_edits_same_channel_stay_sequential():
    actions = [
        {"type": "edit_channel", "params": {"channel": "x", "name": "y"}},
        {"type": "edit_channel", "params": {"channel": "x", "topic": "t"}},
    ]
    assert build_layers(actions) == [[0], [1]]


def test_two_edits_different_channels_run_in_parallel():
    actions = [
        {"type": "edit_channel", "params": {"channel": "x", "name": "y"}},
        {"type": "edit_channel", "params": {"channel": "z", "topic": "t"}},
    ]
    assert build_layers(actions) == [[0, 1]]


def test_set_permissions_waits_for_both_channel_and_role():
    actions = [
        {"type": "create_role", "params": {"name": "Modo"}},
        {"type": "create_text_channel", "params": {"name": "logs"}},
        {
            "type": "set_channel_permissions",
            "params": {"channel": "logs", "role": "Modo", "allow": ["read_messages"]},
        },
    ]
    layers = build_layers(actions)
    assert layers == [[0, 1], [2]]


def test_complex_plan_three_layers():
    actions = [
        {"type": "create_category", "params": {"name": "Communauté"}},
        {"type": "create_role", "params": {"name": "Modo"}},
        {
            "type": "create_text_channel",
            "params": {"name": "annonces", "category": "Communauté"},
        },
        {
            "type": "set_channel_permissions",
            "params": {"channel": "annonces", "role": "Modo"},
        },
    ]
    layers = build_layers(actions)
    # Layer 0: category + role (independent)
    # Layer 1: annonces (needs category)
    # Layer 2: permissions (needs annonces + role)
    assert layers == [[0, 1], [2], [3]]


def test_edit_after_create_same_name_is_two_layers():
    actions = [
        {"type": "create_text_channel", "params": {"name": "ch"}},
        {"type": "edit_channel", "params": {"channel": "ch", "topic": "t"}},
    ]
    assert build_layers(actions) == [[0], [1]]


def test_order_preserved_within_layer():
    actions = [
        {"type": "create_role", "params": {"name": f"R{i}"}}
        for i in range(5)
    ]
    layers = build_layers(actions)
    assert layers == [[0, 1, 2, 3, 4]]
