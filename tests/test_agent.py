import json
import pytest
from pydantic import ValidationError
from unittest.mock import patch

from architect.agent.providers.base import LLMProvider
from architect.models.plan import Plan


class MockProvider(LLMProvider):
    def __init__(self, response: str) -> None:
        self._response = response

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        return self._response


VALID_PLAN_JSON = json.dumps({
    "title": "Gaming Plan",
    "description": "Create a gaming space",
    "actions": [
        {"type": "create_category", "params": {"name": "Gaming"}},
        {"type": "create_text_channel", "params": {"name": "general", "category": "Gaming"}},
    ],
})

INVALID_JSON = "not json at all"

INVALID_ACTION_JSON = json.dumps({
    "title": "T",
    "description": "D",
    "actions": [{"type": "nuke_server", "params": {}}],
})


async def test_generate_plan_valid():
    from architect.agent.agent import ArchitectAgent
    with patch("architect.agent.agent._build_provider", return_value=MockProvider(VALID_PLAN_JSON)):
        agent = ArchitectAgent()
    plan = await agent.generate_plan("Create a gaming space")
    assert isinstance(plan, Plan)
    assert plan.title == "Gaming Plan"
    assert len(plan.actions) == 2


async def test_generate_plan_invalid_json_raises():
    from architect.agent.agent import ArchitectAgent
    with patch("architect.agent.agent._build_provider", return_value=MockProvider(INVALID_JSON)):
        agent = ArchitectAgent()
    with pytest.raises(Exception):
        await agent.generate_plan("prompt")


async def test_generate_plan_unknown_action_raises():
    from architect.agent.agent import ArchitectAgent
    with patch("architect.agent.agent._build_provider", return_value=MockProvider(INVALID_ACTION_JSON)):
        agent = ArchitectAgent()
    with pytest.raises(ValidationError):
        await agent.generate_plan("prompt")
