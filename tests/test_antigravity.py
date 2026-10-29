import json
import subprocess
import sys

import pytest

from scrip_core.adapters import antigravity
from scrip_core.models import Decision, InputRequested


def payload(tmp_path, name="run_command", arguments=None):
    return {
        "conversationId": "session-1",
        "workspacePaths": [str(tmp_path)],
        "stepIdx": 7,
        "toolCall": {
            "name": name,
            "args": arguments or {"CommandLine": "npm test", "Cwd": str(tmp_path)},
        },
    }


def test_question_tool_displays_question_without_answering(tmp_path):
    raw = payload(
        tmp_path,
        "ask_question",
        {
            "questions": [
                {
                    "question": "Which database?",
                    "options": ["SQLite", {"text": "PostgreSQL"}],
                    "is_multi_select": False,
                }
            ]
        },
    )
    event = antigravity.normalize("PreToolUse", raw, "enforce")
    assert isinstance(event, InputRequested)
    assert event.payload.questions[0].options == ["SQLite", "PostgreSQL"]
    response = antigravity.hook_response(
        "PreToolUse",
        event,
        Decision(action="allow", reason="x"),
        "enforce",
    )
    assert response["decision"] == "allow"  # Delegate to the native QUESTION tool.
    assert not any(key in response for key in ("answer", "overwrite", "injectSteps"))


def test_pre_and_post_share_operation_not_event_id(tmp_path):
    pre = antigravity.normalize("PreToolUse", payload(tmp_path))
    retry = antigravity.normalize("PreToolUse", payload(tmp_path))
    post = antigravity.normalize("PostToolUse", payload(tmp_path))
    assert pre.event_id == retry.event_id != post.event_id
    assert pre.operation_id == post.operation_id


def test_enforcement_does_not_confuse_allow_with_auto_approve(tmp_path):
    event = antigravity.normalize("PreToolUse", payload(tmp_path), "enforce")
    for action, expected in (("allow", "auto_approve"), ("deny", "deny"), ("ask", "force_ask")):
        decision = Decision(action=action, reason="rule")
        assert (
            antigravity.hook_response("PreToolUse", event, decision, "enforce")["decision"]
            == expected
        )
        assert (
            antigravity.hook_response("PreToolUse", event, decision, "observe")["decision"]
            == "allow"
        )


def test_invalid_workspace_and_missing_step_cannot_be_approved(tmp_path):
    raw = payload(tmp_path, arguments={"Cwd": str(tmp_path.parent / "outside")})
    with pytest.raises(ValueError, match="outside"):
        antigravity.normalize("PreToolUse", raw)
    raw = payload(tmp_path)
    del raw["stepIdx"]
    with pytest.raises(ValueError, match="stepIdx"):
        antigravity.normalize("PreToolUse", raw)


def test_background_work_is_not_session_completion(tmp_path):
    raw = {
        "conversationId": "c",
        "workspacePaths": [str(tmp_path)],
        "executionNum": 2,
        "fullyIdle": False,
    }
    assert antigravity.normalize("Stop", raw).kind == "session.progress"
    raw["fullyIdle"] = True
    assert antigravity.normalize("Stop", raw).kind == "turn.completed"
    raw["error"] = "Build failed"
    assert antigravity.normalize("Stop", raw).kind == "turn.failed"


@pytest.mark.parametrize("mode,expected", [("observe", "allow"), ("enforce", "force_ask")])
def test_unavailable_service_never_grants_automatic_approval(tmp_path, mode, expected):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scrip_core",
            "--data-dir",
            str(tmp_path / "uninitialized"),
            "hook",
            "antigravity",
            "--event",
            "PreToolUse",
            "--mode",
            mode,
        ],
        input=json.dumps(payload(tmp_path)),
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["decision"] == expected
    assert "no approval granted" in result.stderr
    assert "auto_approve" not in result.stdout
    assert not (tmp_path / "uninitialized").exists()


def test_config_generation_does_not_change_host(tmp_path):
    configuration = antigravity.hook_configuration(tmp_path / "state")
    assert list(tmp_path.iterdir()) == []
    hooks = configuration["scrip-companion"]
    assert "--mode observe" in hooks["PreToolUse"][0]["hooks"][0]["command"]
    assert hooks["PreToolUse"][0]["matcher"] == ".*"
