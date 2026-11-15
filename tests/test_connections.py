import json
import sys
from pathlib import Path

import pytest

from scrip_core.adapters.common import hook_argv
from scrip_core.connections import (
    ConnectionStatus,
    apply_connection,
    connection_status,
    disconnect,
    plan_connection,
    receipt_path,
)


def test_connection_preserves_settings_and_other_hooks_and_disconnects_only_ours(tmp_path):
    workspace = tmp_path / "project with spaces"
    workspace.mkdir()
    folder = workspace / ".claude"
    folder.mkdir()
    settings = folder / "settings.local.json"
    existing = {
        "permissions": {"allow": ["Read"]},
        "hooks": {
            "SessionStart": [{"hooks": [{"type": "command", "command": "echo existing"}]}],
        },
    }
    settings.write_text(json.dumps(existing))
    state = tmp_path / "state"
    plan = plan_connection(workspace, state, "observe")
    assert json.loads(settings.read_text()) == existing  # Review has no side effects.
    apply_connection(plan, state)
    apply_connection(plan_connection(workspace, state, "observe"), state)
    doc = json.loads(settings.read_text())
    assert doc["permissions"] == existing["permissions"]
    assert len(doc["hooks"]["SessionStart"]) == 2
    assert connection_status(state) == [
        ConnectionStatus(str(workspace), "claude-code", "observe", "Configured")
    ]
    doc["newSetting"] = True
    settings.write_text(json.dumps(doc))
    disconnect(workspace, state)
    assert json.loads(settings.read_text()) == {**existing, "newSetting": True}
    assert connection_status(state) == []
    assert list(folder.glob("*.scrip-backup-*"))


def test_connect_refuses_stale_review_and_mode_changes(tmp_path):
    workspace = tmp_path / "project"
    workspace.mkdir()
    state = tmp_path / "state"
    plan = plan_connection(workspace, state, "observe")
    plan.target.parent.mkdir()
    plan.target.write_text('{"changed": true}')
    with pytest.raises(ValueError, match="changed since review"):
        apply_connection(plan, state)
    assert json.loads(plan.target.read_text()) == {"changed": True}
    apply_connection(plan_connection(workspace, state, "observe"), state)
    with pytest.raises(ValueError, match="Disconnect"):
        apply_connection(plan_connection(workspace, state, "enforce"), state)


def test_connection_refuses_invalid_settings_without_overwriting_them(tmp_path):
    folder = tmp_path / ".claude"
    folder.mkdir()
    target = folder / "settings.local.json"
    target.write_text('{"hooks": {"SessionStart": "invalid"}}')
    with pytest.raises(ValueError):
        plan_connection(tmp_path, tmp_path / "state", "observe")
    assert json.loads(target.read_text())["hooks"]["SessionStart"] == "invalid"


def test_frozen_hook_uses_console_executable_not_python_module_flags(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Scrip.exe"))
    command = hook_argv("claude-code", "PreToolUse", tmp_path, "observe")
    assert Path(command[0]).stem == "scrip-cli"
    assert "-m" not in command
    assert command[-1] == "observe"


@pytest.mark.parametrize("adapter", ["claude-code", "cursor"])
def test_connection_owns_only_added_entries_and_keeps_later_user_hooks(tmp_path, adapter):
    state = tmp_path / "state"
    first = plan_connection(tmp_path, state, "observe", adapter)
    first.target.parent.mkdir()
    # Exact entries can already have been installed manually; they are not ours to remove.
    name = next(iter(first.entries))
    existing = {"hooks": {name: first.entries[name]}, "custom": True}
    if adapter == "cursor":
        existing["version"] = 1
    first.target.write_text(json.dumps(existing))
    plan = plan_connection(tmp_path, state, "observe", adapter)
    apply_connection(plan, state)
    doc = json.loads(plan.target.read_text())
    doc["hooks"][name].append({"command": "user-owned"})
    plan.target.write_text(json.dumps(doc))
    disconnect(tmp_path, state, adapter)
    existing["hooks"][name].append({"command": "user-owned"})
    assert json.loads(plan.target.read_text()) == existing


def test_two_hosts_in_one_workspace_have_independent_ownership(tmp_path):
    state = tmp_path / "state"
    claude = plan_connection(tmp_path, state, "observe")
    cursor = plan_connection(tmp_path, state, "enforce", "cursor")
    apply_connection(claude, state)
    apply_connection(cursor, state)
    assert len(connection_status(state)) == 2
    disconnect(tmp_path, state, "cursor")
    assert claude.target.read_text() == claude.content
    assert connection_status(state) == [
        ConnectionStatus(str(tmp_path), "claude-code", "observe", "Configured")
    ]


def test_existing_released_claude_receipt_still_disconnects(tmp_path):
    state = tmp_path / "state"
    plan = plan_connection(tmp_path, state, "observe")
    apply_connection(plan, state)
    receipt = receipt_path(state, tmp_path)
    doc = json.loads(receipt.read_text())
    del doc["adapter"]
    del doc["expected"]
    receipt.write_text(json.dumps(doc))
    assert connection_status(state)[0].status == "Configured"
    disconnect(tmp_path, state)
    assert json.loads(plan.target.read_text()) == {"hooks": {}}


@pytest.mark.parametrize("version", [True, 2, "1"])
def test_cursor_refuses_unknown_configuration_versions(tmp_path, version):
    folder = tmp_path / ".cursor"
    folder.mkdir()
    target = folder / "hooks.json"
    original = json.dumps({"version": version})
    target.write_text(original)
    with pytest.raises(ValueError, match="version"):
        plan_connection(tmp_path, tmp_path / "state", "observe", "cursor")
    assert target.read_text() == original


def test_cursor_stale_review_does_not_overwrite_changes(tmp_path):
    state = tmp_path / "state"
    plan = plan_connection(tmp_path, state, "observe", "cursor")
    plan.target.parent.mkdir()
    plan.target.write_text('{"version":1,"user":true}')
    with pytest.raises(ValueError, match="changed since review"):
        apply_connection(plan, state)
    assert json.loads(plan.target.read_text())["user"] is True


def test_disconnect_does_not_recreate_deleted_host_configuration(tmp_path):
    state = tmp_path / "state"
    plan = plan_connection(tmp_path, state, "observe", "cursor")
    apply_connection(plan, state)
    plan.target.unlink()
    plan.target.parent.rmdir()
    disconnect(tmp_path, state, "cursor")
    assert not plan.target.parent.exists()
    assert connection_status(state) == []
