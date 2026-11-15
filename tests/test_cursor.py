import json
import os
import re
import subprocess
import sys

import pytest

from devtools.process import invoke_hook, running_service
from scrip_core.adapters import cursor
from scrip_core.errors import ConflictError
from scrip_core.models import Decision
from tests.factories import rule_for


def payload(workspace, **extra):
    return {
        "conversation_id": "cursor-session",
        "generation_id": "generation-1",
        "workspace_roots": [str(workspace)],
        "command": "NEVER_EXECUTE_THIS_PROPOSED_COMMAND",
        "cwd": str(workspace),
        "sandbox": True,
        **extra,
    }


def test_configuration_separates_visibility_from_native_permission_hooks(tmp_path):
    observed = cursor.hook_configuration(tmp_path)["hooks"]
    enforced = cursor.hook_configuration(tmp_path, "enforce")["hooks"]
    assert set(observed) == set(cursor.OBSERVATION_HOOKS)
    assert "preToolUse" not in enforced
    for hook in cursor.PERMISSION_HOOKS:
        assert enforced[hook][0]["failClosed"] is True
        assert cursor.unavailable_response(hook)["permission"] == "ask"
    matcher = enforced["postToolUse"][0]["matcher"]
    assert re.search(matcher, "Read")
    assert not re.search(matcher, "Shell")
    assert not re.search(matcher, "MCP:search")
    assert not cursor.CAPABILITIES.structured_questions


@pytest.mark.parametrize("action", ["allow", "deny", "ask"])
def test_native_decisions_are_explicit_and_observe_cannot_allow(tmp_path, action):
    event = cursor.normalize("beforeShellExecution", payload(tmp_path), "enforce")
    decision = Decision(action=action, reason="exact policy")
    assert cursor.hook_response("beforeShellExecution", event, decision, "enforce") == {
        "permission": action,
        "user_message": "exact policy",
    }
    assert (
        cursor.hook_response("beforeShellExecution", event, decision, "observe")["permission"]
        == "ask"
    )
    assert cursor.hook_response("postToolUse", event, decision, "enforce") == {}


def test_approval_once_per_generation_and_changed_scope_conflicts(companion, tmp_path):
    raw = payload(tmp_path)
    event = cursor.normalize("beforeShellExecution", raw, "enforce")
    companion.put_rule(rule_for(event))
    assert companion.ingest(event).decision.action == "allow"
    assert companion.ingest(event).decision.action == "ask"
    changed = cursor.normalize("beforeShellExecution", {**raw, "sandbox": False}, "enforce")
    with pytest.raises(ConflictError):
        companion.ingest(changed)
    next_turn = cursor.normalize(
        "beforeShellExecution", {**raw, "generation_id": "next"}, "enforce"
    )
    assert companion.ingest(next_turn).decision.action == "allow"


@pytest.mark.parametrize(
    "changes",
    [
        {"workspace_roots": []},
        {"generation_id": ""},
        {"sandbox": 1},
        {"session_id": "different"},
        {"hook_event_name": "postToolUse"},
        {"cwd": ""},
    ],
)
def test_rejects_ambiguous_permission_context(tmp_path, changes):
    with pytest.raises(ValueError):
        cursor.normalize("beforeShellExecution", payload(tmp_path, **changes), "enforce")


def test_rejects_multiroot_outside_directory_and_remote(tmp_path, monkeypatch):
    raw = payload(tmp_path)
    for changes in (
        {"workspace_roots": [str(tmp_path), str(tmp_path.parent)]},
        {"cwd": str(tmp_path.parent)},
    ):
        with pytest.raises(ValueError):
            cursor.normalize("beforeShellExecution", {**raw, **changes})
    monkeypatch.setenv("CURSOR_CODE_REMOTE", "true")
    with pytest.raises(ValueError, match="Remote"):
        cursor.normalize("sessionStart", raw)


def mcp_payload(workspace, **extra):
    return payload(
        workspace,
        command="server-launch",
        mcp_server_name="documents",
        tool_name="search",
        tool_input='{"query":"scrip"}',
        **extra,
    )


def test_mcp_rules_bind_endpoint_server_and_full_input(companion, tmp_path):
    raw = mcp_payload(tmp_path, mcp_server_url="https://one.invalid/mcp")
    event = cursor.normalize("beforeMCPExecution", raw, "enforce")
    companion.put_rule(rule_for(event))
    assert companion.ingest(event).decision.action == "allow"
    for change in (
        {"mcp_server_name": "other"},
        {"mcp_server_url": "https://two.invalid/mcp"},
        {"tool_input": '{"query":"other"}'},
    ):
        changed = cursor.normalize(
            "beforeMCPExecution", {**raw, **change, "generation_id": "next"}, "enforce"
        )
        assert companion.ingest(changed).decision.action == "ask"


@pytest.mark.parametrize(
    "changes",
    [
        {"tool_input": "[]"},
        {"tool_input": "invalid"},
        {"command": "", "mcp_server_url": ""},
        {"url": "https://one.invalid", "mcp_server_url": "https://two.invalid"},
    ],
)
def test_invalid_mcp_context_rejected(tmp_path, changes):
    with pytest.raises(ValueError):
        cursor.normalize("beforeMCPExecution", {**mcp_payload(tmp_path), **changes})


@pytest.mark.parametrize(
    "before,after",
    [("beforeShellExecution", "afterShellExecution"), ("beforeMCPExecution", "afterMCPExecution")],
)
def test_native_completion_resolves_request_and_drops_outputs(companion, tmp_path, before, after):
    raw = payload(tmp_path) if "Shell" in before else mcp_payload(tmp_path)
    requested = cursor.normalize(before, raw, "enforce")
    companion.ingest(requested)
    assert len(companion.inbox()) == 1
    completed = cursor.normalize(
        after, {**raw, "output": "SECRET", "result_json": "SECRET", "user_email": "SECRET"}
    )
    assert completed.operation_id == requested.operation_id
    assert "SECRET" not in completed.model_dump_json()
    companion.ingest(completed)
    assert companion.inbox() == []


def test_turn_completion_keeps_session_open_and_failure_creates_alert(companion, tmp_path):
    raw = payload(tmp_path)
    companion.ingest(cursor.normalize("sessionStart", raw))
    companion.ingest(cursor.normalize("stop", {**raw, "status": "error", "loop_count": 0}))
    assert companion.sessions()[0].state == "idle"
    assert companion.notifications()[0].kind == "failure"
    companion.ingest(
        cursor.normalize("beforeShellExecution", {**raw, "generation_id": "new"}, "enforce")
    )
    assert companion.sessions()[0].state == "waiting_permission"
    companion.ingest(cursor.normalize("sessionEnd", {**raw, "reason": "user_close"}))
    assert companion.sessions()[0].state == "completed"


def test_generated_command_reaches_authenticated_service_without_executing_proposal(tmp_path):
    with running_service(tmp_path) as running:
        config = cursor.hook_configuration(running.settings.data_dir, "enforce")
        command = config["hooks"]["beforeShellExecution"][0]["command"]
        argv = (
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
            if os.name == "nt"
            else ["sh", "-c", command]
        )
        raw = payload(tmp_path)
        assert (
            invoke_hook(running.settings, "cursor", raw, "beforeShellExecution", command=argv)[
                "permission"
            ]
            == "ask"
        )
        assert len(running.companion.inbox()) == 1
        event = cursor.normalize("beforeShellExecution", raw, "enforce")
        running.companion.put_rule(rule_for(event))
        raw["generation_id"] = "allowed-turn"
        assert (
            invoke_hook(running.settings, "cursor", raw, "beforeShellExecution", command=argv)[
                "permission"
            ]
            == "allow"
        )
        assert (
            invoke_hook(running.settings, "cursor", raw, "beforeShellExecution", command=argv)[
                "permission"
            ]
            == "ask"
        )
        running.companion.put_rule(rule_for(event).model_copy(update={"action": "deny"}))
        raw["generation_id"] = "denied-turn"
        assert (
            invoke_hook(running.settings, "cursor", raw, "beforeShellExecution", command=argv)[
                "permission"
            ]
            == "deny"
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell literal argument transport")
def test_powershell_arguments_roundtrip_without_interpretation(tmp_path):
    script = tmp_path / "capture args.py"
    script.write_text("import json,sys; print(json.dumps(sys.argv[1:]))")
    values = ["with spaces", "O'Brien", "$env:PATH", "$(Write-Output injected)", "a&b;exit"]
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            cursor.powershell_command([sys.executable, str(script), *values]),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    assert json.loads(result.stdout) == values


def test_unavailable_service_returns_native_review_without_initializing_state(tmp_path):
    from scrip_core.adapters.common import hook_argv

    state = tmp_path / "not-initialized"
    result = subprocess.run(
        hook_argv("cursor", "beforeShellExecution", state, "enforce"),
        input=json.dumps(payload(tmp_path)),
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["permission"] == "ask"
    assert "no approval granted" in result.stderr
    assert not state.exists()


def test_generic_completed_tools_are_visibility_only_and_strip_output(companion, tmp_path):
    raw = payload(
        tmp_path,
        tool_name="Read",
        tool_input={"path": "source.py"},
        tool_use_id="read-1",
        tool_output="PRIVATE OUTPUT",
    )
    event = cursor.normalize("postToolUse", raw)
    companion.ingest(event)
    assert "PRIVATE OUTPUT" not in event.model_dump_json()
    assert companion.inbox() == []
    assert companion.notifications() == []
