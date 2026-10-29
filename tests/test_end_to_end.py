"""Real CLI and loopback transport tests; no host application is opened."""

import pytest

from devtools.process import invoke_hook, running_service
from scrip_core.adapters.antigravity import hook_configuration
from scrip_core.models import Rule


@pytest.fixture
def service(tmp_path):
    with running_service(tmp_path) as local:
        yield local.settings, local.client, local.companion, local.workspace


def call_hook(settings, payload, hook="PreToolUse", mode="enforce"):
    config = hook_configuration(settings.data_dir, mode)["scrip-companion"]
    handlers = config[hook]
    handler = handlers[0]["hooks"][0] if hook in ("PreToolUse", "PostToolUse") else handlers[0]
    return invoke_hook(settings, "antigravity", payload, hook, mode, command=handler["command"])


def test_real_transport_policy_question_and_completion(service):
    settings, client, store, workspace = service
    payload = {
        "conversationId": "demo",
        "workspacePaths": [str(workspace)],
        "stepIdx": 0,
        "toolCall": {
            "name": "run_command",
            "args": {"CommandLine": "npm test", "Cwd": str(workspace)},
        },
    }
    assert call_hook(settings, payload)["decision"] == "force_ask"
    assert len(client.request("/v1/inbox")["items"]) == 1
    store.put_rule(
        Rule(
            id="explicit-task",
            adapter="antigravity",
            workspace=str(workspace),
            tool="run_command",
            arguments=payload["toolCall"]["args"],
            action="allow",
        )
    )
    payload["stepIdx"] = 1
    assert call_hook(settings, payload)["decision"] == "auto_approve"
    assert call_hook(settings, payload)["decision"] == "force_ask"
    payload["stepIdx"] = 2
    payload["toolCall"] = {
        "name": "ask_question",
        "args": {
            "questions": [
                {"question": "Which database?", "options": ["SQLite", "PostgreSQL"]},
            ]
        },
    }
    assert call_hook(settings, payload)["decision"] == "allow"
    assert any(item["kind"] == "input" for item in client.request("/v1/inbox")["items"])
    assert call_hook(settings, payload, "PostToolUse") == {}
    assert not any(item["kind"] == "input" for item in client.request("/v1/inbox")["items"])
    client.request("/v1/health")


def test_observation_is_non_controlling_over_real_transport(service):
    settings, client, _store, workspace = service
    payload = {
        "conversationId": "observer",
        "workspacePaths": [str(workspace)],
        "stepIdx": 0,
        "toolCall": {"name": "run_command", "args": {"CommandLine": "unreviewed command"}},
    }
    assert call_hook(settings, payload, mode="observe")["decision"] == "allow"
    assert client.request("/v1/inbox")["items"] == []
    assert client.request("/v1/notifications")["items"] == []


def test_second_host_uses_same_core_through_its_own_protocol(service):
    from scrip_core.adapters import claude_code

    settings, client, store, workspace = service
    config = claude_code.hook_configuration(settings.data_dir, "enforce")["hooks"]

    def invoke(hook, payload):
        command = config[hook][0]["hooks"][0]["command"]
        return invoke_hook(settings, "claude-code", payload, hook, command=command)

    raw = {
        "session_id": "claude-demo",
        "cwd": str(workspace),
        "tool_use_id": "toolu_1",
        "tool_name": "Bash",
        "tool_input": {"command": "npm test"},
    }
    assert invoke("PreToolUse", raw)["hookSpecificOutput"]["permissionDecision"] == "ask"
    store.put_rule(
        Rule(
            id="claude-task",
            adapter="claude-code",
            workspace=str(workspace),
            tool="Bash",
            arguments={"command": "npm test"},
            action="allow",
        )
    )
    raw["tool_use_id"] = "toolu_2"
    assert invoke("PreToolUse", raw)["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert invoke("PreToolUse", raw)["hookSpecificOutput"]["permissionDecision"] == "ask"
    raw["tool_use_id"] = "toolu_3"
    raw["tool_name"] = "AskUserQuestion"
    raw["tool_input"] = {"questions": [{"question": "Continue?", "options": []}]}
    assert invoke("PreToolUse", raw) == {}
    assert any(row["kind"] == "input" for row in client.request("/v1/inbox")["items"])
    assert invoke("PostToolUse", raw) == {}
    assert not any(row["kind"] == "input" for row in client.request("/v1/inbox")["items"])
    assert invoke("Stop", {"session_id": "claude-demo", "cwd": str(workspace)}) == {}
    assert store.sessions()[0].state == "idle"
