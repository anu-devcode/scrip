from datetime import timedelta

import pytest
from pydantic import ValidationError

from scrip_core.models import Tool, utc_now
from scrip_core.policy import decide
from tests.factories import rule_for


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_arguments_are_rejected_in_nested_payloads(tool_event, number):
    with pytest.raises(ValidationError):
        Tool(name="run_command", arguments={"nested": [number]})
    with pytest.raises(ValidationError):
        rule_for(tool_event, arguments={"nested": {"value": number}})


def test_only_exact_action_is_allowed(tool_event):
    rule = rule_for(tool_event)
    assert decide(tool_event, []).action == "ask"
    assert decide(tool_event, [rule]).action == "allow"
    changed = tool_event.model_copy(
        update={
            "payload": Tool(
                name="run_command",
                arguments={
                    **tool_event.payload.arguments,
                    "CommandLine": "npm test; git push",
                },
            )
        }
    )
    assert decide(changed, [rule]).action == "ask"
    extra_flag = tool_event.model_copy(
        update={
            "payload": Tool(
                name="run_command",
                arguments={
                    **tool_event.payload.arguments,
                    "BypassSandbox": True,
                },
            )
        }
    )
    assert decide(extra_flag, [rule]).action == "ask"


def test_deny_wins_and_pause_preserves_deny(tool_event):
    allow = rule_for(tool_event)
    deny = rule_for(tool_event, id="deny-task", action="deny")
    assert decide(tool_event, [allow, deny]).action == "deny"
    assert decide(tool_event, [allow], paused=True).action == "ask"
    assert decide(tool_event, [allow, deny], paused=True).action == "deny"


def test_workspace_session_adapter_and_expiry_are_bound(tool_event, tmp_path):
    rules = [
        rule_for(tool_event, workspace=str(tmp_path / "another-project")),
        rule_for(tool_event, session_id="another-session"),
        rule_for(tool_event, adapter="another-agent"),
        rule_for(tool_event, expires_at=utc_now() - timedelta(seconds=1)),
        rule_for(tool_event, enabled=False),
    ]
    for rule in rules:
        assert decide(tool_event, [rule]).action == "ask"


def test_boolean_and_number_are_not_interchangeable(tool_event):
    event = tool_event.model_copy(
        update={"payload": Tool(name="run_command", arguments={"x": True})}
    )
    assert decide(event, [rule_for(event, arguments={"x": 1})]).action == "ask"


def test_questions_cannot_receive_approval_rules(tool_event):
    with pytest.raises(ValidationError, match="Questions cannot"):
        rule_for(tool_event, tool="ask_question")
    event = tool_event.model_copy(update={"payload": Tool(name="ask_question", arguments={})})
    assert decide(event, [rule_for(tool_event)]).action == "ask"
