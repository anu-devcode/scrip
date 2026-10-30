import pytest

from scrip_core.adapters import claude_code
from scrip_core.models import Decision, InputRequested


def payload(tmp_path, tool="Bash", arguments=None):
    return {
        "session_id": "claude-session",
        "cwd": str(tmp_path),
        "tool_use_id": "toolu_123",
        "tool_name": tool,
        "tool_input": arguments or {"command": "npm test"},
    }


def test_native_claude_question_is_observed_but_never_answered(tmp_path):
    raw = payload(
        tmp_path,
        "AskUserQuestion",
        {
            "questions": [
                {
                    "question": "Which database?",
                    "header": "Database",
                    "multiSelect": False,
                    "options": [
                        {"label": "SQLite", "description": "Local"},
                        {"label": "PostgreSQL", "description": "Server"},
                    ],
                }
            ]
        },
    )
    event = claude_code.normalize("PreToolUse", raw, "enforce")
    assert isinstance(event, InputRequested)
    assert event.payload.questions[0].options == ["SQLite", "PostgreSQL"]
    assert (
        claude_code.hook_response(
            "PreToolUse",
            event,
            Decision(action="allow", reason="x"),
            "enforce",
        )
        == {}
    )


def test_native_permission_decisions_and_observer_mode(tmp_path):
    event = claude_code.normalize("PreToolUse", payload(tmp_path), "enforce")
    for action in ("allow", "deny", "ask"):
        response = claude_code.hook_response(
            "PreToolUse",
            event,
            Decision(action=action, reason="rule"),
            "enforce",
        )
        assert response["hookSpecificOutput"]["permissionDecision"] == action
        assert (
            claude_code.hook_response(
                "PreToolUse",
                event,
                Decision(action=action, reason="rule"),
                "observe",
            )
            == {}
        )


def test_tool_identity_and_payload_event_name_are_validated(tmp_path):
    raw = payload(tmp_path)
    pre = claude_code.normalize("PreToolUse", raw)
    post = claude_code.normalize("PostToolUse", raw)
    assert pre.operation_id == post.operation_id
    assert pre.event_id != post.event_id
    del raw["tool_use_id"]
    with pytest.raises(ValueError, match="tool_use_id"):
        claude_code.normalize("PreToolUse", raw)
    raw["hook_event_name"] = "PostToolUse"
    with pytest.raises(ValueError, match="does not match"):
        claude_code.normalize("PreToolUse", raw)


def test_stop_is_turn_completion_not_session_end(tmp_path):
    raw = {"session_id": "s", "cwd": str(tmp_path)}
    assert claude_code.normalize("Stop", raw).kind == "turn.completed"
    assert claude_code.normalize("SessionEnd", raw).kind == "session.completed"
    raw["background_tasks"] = [{"id": "background"}]
    assert claude_code.normalize("Stop", raw).kind == "session.progress"


def test_hook_configuration_is_only_generated(tmp_path):
    config = claude_code.hook_configuration(tmp_path)
    assert list(tmp_path.iterdir()) == []
    assert "hooks" in config
    handler = config["hooks"]["PreToolUse"][0]["hooks"][0]
    assert handler["args"][handler["args"].index("hook") + 1] == "claude-code"
    assert handler["onFailure"] == "continue"
    enforcing = claude_code.hook_configuration(tmp_path, "enforce")
    assert enforcing["hooks"]["PreToolUse"][0]["hooks"][0]["onFailure"] == "block"
    assert claude_code.unavailable_response("PreToolUse", "observe") == {}
    assert (
        claude_code.unavailable_response(
            "PreToolUse",
            "enforce",
        )["hookSpecificOutput"]["permissionDecision"]
        == "ask"
    )
