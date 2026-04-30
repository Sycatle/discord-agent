"""Validation tests for the per-action Pydantic parameter models.

The whole purpose of these models is to refuse anything outside the explicit
whitelist. The tests focus on three invariants:

- required fields raise when missing,
- extra fields are forbidden,
- typed fields (literals, ranges) reject invalid values.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from architect.models.params import (
    AssignRoleParams,
    CreateAutoModRuleParams,
    CreateCategoryParams,
    CreateForumChannelParams,
    CreateInviteParams,
    CreateRoleParams,
    CreateScheduledEventParams,
    CreateStageChannelParams,
    CreateTextChannelParams,
    CreateVoiceChannelParams,
    CreateWebhookParams,
    DeleteAutoModRuleParams,
    DeleteChannelParams,
    DeleteInviteParams,
    DeleteRoleParams,
    DeleteScheduledEventParams,
    DeleteWebhookParams,
    EditAutoModRuleParams,
    EditChannelParams,
    EditMemberParams,
    EditRoleParams,
    EditScheduledEventParams,
    EditServerParams,
    EditWebhookParams,
    EditWelcomeScreenParams,
    RemoveRoleParams,
    SetChannelPermissionsParams,
    WelcomeChannelEntry,
)

# ── Channels ────────────────────────────────────────────────────────────────


def test_create_category_requires_name():
    with pytest.raises(ValidationError):
        CreateCategoryParams()  # type: ignore[call-arg]


def test_create_category_forbids_extra():
    with pytest.raises(ValidationError):
        CreateCategoryParams(name="cat", color="red")  # type: ignore[call-arg]


def test_create_text_channel_minimal_and_with_category():
    assert CreateTextChannelParams(name="general").category is None
    assert CreateTextChannelParams(name="news", category="Info").category == "Info"


def test_create_voice_channel_minimal():
    assert CreateVoiceChannelParams(name="Voice").category is None


def test_create_forum_channel_validates_slowmode_range():
    CreateForumChannelParams(name="f", slowmode=0)
    CreateForumChannelParams(name="f", slowmode=21600)
    with pytest.raises(ValidationError):
        CreateForumChannelParams(name="f", slowmode=21601)


def test_create_forum_channel_rejects_unknown_sort_order():
    with pytest.raises(ValidationError):
        CreateForumChannelParams(name="f", default_sort_order="oldest")  # type: ignore[arg-type]


def test_create_forum_channel_caps_tags_at_20():
    CreateForumChannelParams(name="f", available_tags=["t"] * 20)
    with pytest.raises(ValidationError):
        CreateForumChannelParams(name="f", available_tags=["t"] * 21)


def test_create_stage_channel_user_limit_bounds():
    CreateStageChannelParams(name="s", user_limit=10000)
    with pytest.raises(ValidationError):
        CreateStageChannelParams(name="s", user_limit=10001)


def test_edit_channel_requires_target():
    with pytest.raises(ValidationError):
        EditChannelParams()  # type: ignore[call-arg]


def test_edit_channel_user_limit_voice_cap():
    EditChannelParams(channel="ch", user_limit=99)
    with pytest.raises(ValidationError):
        EditChannelParams(channel="ch", user_limit=100)


def test_edit_channel_unknown_video_quality_mode():
    with pytest.raises(ValidationError):
        EditChannelParams(channel="ch", video_quality_mode="ultra")  # type: ignore[arg-type]


def test_delete_channel_optional_reason():
    p = DeleteChannelParams(channel="ch")
    assert p.reason is None


def test_set_channel_permissions_requires_channel_and_role():
    with pytest.raises(ValidationError):
        SetChannelPermissionsParams(channel="ch")  # type: ignore[call-arg]


def test_create_invite_max_age_bounds():
    CreateInviteParams(channel="ch", max_age=604800)
    with pytest.raises(ValidationError):
        CreateInviteParams(channel="ch", max_age=604801)


def test_delete_invite_requires_code():
    with pytest.raises(ValidationError):
        DeleteInviteParams()  # type: ignore[call-arg]


def test_create_webhook_requires_channel_and_name():
    with pytest.raises(ValidationError):
        CreateWebhookParams(channel="ch")  # type: ignore[call-arg]


def test_edit_webhook_requires_target():
    EditWebhookParams(webhook="wh", name="renamed")
    with pytest.raises(ValidationError):
        EditWebhookParams()  # type: ignore[call-arg]


def test_delete_webhook_minimal():
    DeleteWebhookParams(webhook="wh")


# ── Roles ───────────────────────────────────────────────────────────────────


def test_create_role_color_accepts_str_or_int():
    CreateRoleParams(name="Mod", color="#ff0000")
    CreateRoleParams(name="Mod", color=0xFF0000)


def test_edit_role_requires_role():
    with pytest.raises(ValidationError):
        EditRoleParams()  # type: ignore[call-arg]


def test_delete_role_requires_role():
    with pytest.raises(ValidationError):
        DeleteRoleParams()  # type: ignore[call-arg]


def test_assign_and_remove_role_require_user_and_role():
    AssignRoleParams(user="<@1>", role="Mod")
    RemoveRoleParams(user="<@1>", role="Mod")
    with pytest.raises(ValidationError):
        AssignRoleParams(user="<@1>")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        RemoveRoleParams(user="<@1>")  # type: ignore[call-arg]


# ── Members ─────────────────────────────────────────────────────────────────


def test_edit_member_requires_user():
    with pytest.raises(ValidationError):
        EditMemberParams()  # type: ignore[call-arg]


def test_edit_member_accepts_partial_payload():
    p = EditMemberParams(user="<@1>", nick="Bob")
    assert p.mute is None and p.deaf is None and p.timeout_until is None


# ── Scheduled events ────────────────────────────────────────────────────────


def test_create_scheduled_event_external_requires_location_via_handler():
    # Pydantic alone can't enforce "location required when external" — that
    # cross-field rule is a handler concern. The model just validates types.
    p = CreateScheduledEventParams(
        name="Game Night",
        start_time="2026-05-01T18:00:00Z",
        entity_type="external",
    )
    assert p.location is None


def test_create_scheduled_event_rejects_unknown_entity_type():
    with pytest.raises(ValidationError):
        CreateScheduledEventParams(
            name="x",
            start_time="2026-05-01T18:00:00Z",
            entity_type="audio",  # type: ignore[arg-type]
        )


def test_edit_scheduled_event_status_literal():
    EditScheduledEventParams(event="Game Night", status="active")
    with pytest.raises(ValidationError):
        EditScheduledEventParams(event="Game Night", status="paused")  # type: ignore[arg-type]


def test_delete_scheduled_event_minimal():
    DeleteScheduledEventParams(event="Game Night")


# ── AutoMod ─────────────────────────────────────────────────────────────────


def test_create_automod_rule_requires_actions():
    with pytest.raises(ValidationError):
        CreateAutoModRuleParams(  # type: ignore[call-arg]
            name="r",
            event_type="message_send",
            trigger_type="keyword",
        )


def test_create_automod_rule_actions_accepts_encoded_strings():
    p = CreateAutoModRuleParams(
        name="r",
        event_type="message_send",
        trigger_type="keyword",
        actions=["block_message", "send_alert:#mod-log", "timeout:300"],
    )
    assert p.actions == ["block_message", "send_alert:#mod-log", "timeout:300"]


def test_create_automod_rule_caps_exempt_lists():
    CreateAutoModRuleParams(
        name="r",
        event_type="message_send",
        trigger_type="keyword",
        actions=["block_message"],
        exempt_roles=["r"] * 20,
        exempt_channels=["c"] * 50,
    )
    with pytest.raises(ValidationError):
        CreateAutoModRuleParams(
            name="r",
            event_type="message_send",
            trigger_type="keyword",
            actions=["block_message"],
            exempt_roles=["r"] * 21,
        )


def test_edit_automod_rule_partial_payload():
    EditAutoModRuleParams(rule="no-spam", enabled=False)


def test_delete_automod_rule_minimal():
    DeleteAutoModRuleParams(rule="no-spam")


# ── Server ──────────────────────────────────────────────────────────────────


def test_edit_server_rejects_unknown_verification_level():
    with pytest.raises(ValidationError):
        EditServerParams(verification_level="paranoid")  # type: ignore[arg-type]


def test_edit_server_accepts_full_payload():
    EditServerParams(
        name="My Server",
        verification_level="medium",
        default_message_notifications="only_mentions",
        explicit_content_filter="all_members",
        afk_channel="afk",
        afk_timeout=60,
        system_channel="general",
        rules_channel="rules",
        public_updates_channel="updates",
        safety_alerts_channel="alerts",
        description="A server",
        preferred_locale="fr",
        premium_progress_bar_enabled=True,
        community=True,
    )


def test_welcome_channel_entry_requires_channel_and_description():
    with pytest.raises(ValidationError):
        WelcomeChannelEntry(channel="ch")  # type: ignore[call-arg]


def test_edit_welcome_screen_with_nested_entries():
    p = EditWelcomeScreenParams(
        enabled=True,
        description="Welcome!",
        welcome_channels=[
            WelcomeChannelEntry(channel="rules", description="Read the rules", emoji="📜"),
            WelcomeChannelEntry(channel="general", description="Say hi"),
        ],
    )
    assert p.welcome_channels is not None
    assert p.welcome_channels[0].emoji == "📜"
    assert p.welcome_channels[1].emoji is None
