import json
import sys
from pathlib import Path

import pytest

from scrip_core.adapters.common import hook_argv
from scrip_core.connections import (
    apply_connection,
    connection_status,
    disconnect,
    plan_connection,
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
    assert connection_status(state) == [(str(workspace), "observe", "Configured")]
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
