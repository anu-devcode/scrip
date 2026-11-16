"""Isolated project setup and real hook processes. Proposed commands are never executed."""

import base64
import json
import os
import shlex
import subprocess
import sys

import pytest

from scrip_core import cli, project
from scrip_core.adapters import common
from scrip_core.bootstrap import create_service

COMMAND = 'git grep -n "staffPortalRoutes"'


def setup(tmp_path):
    workspace = tmp_path / "project with spaces"
    workspace.mkdir()
    base = tmp_path / "private-state"
    plan = project.plan_setup(workspace, base, [COMMAND])
    project.apply_setup(plan, base, confirmed=True)
    return workspace, base, plan


def payload(workspace, index=1, **arguments):
    return {
        "conversationId": "real-hook-process",
        "workspacePaths": [str(workspace)],
        "stepIdx": index,
        "toolCall": {
            "name": "run_command",
            "args": {
                "CommandLine": COMMAND,
                "Cwd": str(workspace),
                "WaitMsBeforeAsync": 500,
                **arguments,
            },
        },
    }


def invoke(plan, raw):
    config = plan.record.entry["PreToolUse"][0]["hooks"][0]["command"]
    launcher = (
        ["cmd.exe", "/D", "/S", "/C", config] if os.name == "nt" else ["/bin/sh", "-c", config]
    )
    result = subprocess.run(
        launcher,
        input=json.dumps(raw, ensure_ascii=False),
        encoding="utf-8",
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_project_hook_runs_without_scrip_on_path(tmp_path, monkeypatch):
    workspace, base, plan = setup(tmp_path)
    windows_shell = os.path.join(
        os.environ.get("SYSTEMROOT", "C:\\Windows"), "System32", "WindowsPowerShell", "v1.0"
    )
    monkeypatch.setenv("PATH", windows_shell if os.name == "nt" else "")
    project.start(workspace, base)
    assert invoke(plan, payload(workspace))["decision"] == "auto_approve"
    assert project.status(workspace, base)["last_hook"] is not None


def test_frozen_project_hook_quotes_absolute_companion_path(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    executable = tmp_path / "Scrip's runtime & tools" / "scrip.exe"
    monkeypatch.setattr(common.sys, "executable", str(executable))
    monkeypatch.setattr(common.sys, "frozen", True, raising=False)
    plan = project.plan_setup(workspace, tmp_path / "state", [])
    config = plan.record.entry["PreToolUse"][0]["hooks"][0]["command"]
    companion = executable.with_name("scrip-cli.exe" if os.name == "nt" else "scrip-cli")
    if os.name == "nt":
        assert config.startswith("powershell.exe -NoProfile -NonInteractive -EncodedCommand ")
        assert '"' not in config
        script = base64.b64decode(config.split()[-1]).decode("utf-16le")
        assert "& '" + str(companion).replace("'", "''") + "' 'project-hook' " in script
        assert "[Console]::In.ReadToEnd() | & " in script
        assert script.endswith("; exit $LASTEXITCODE")
    else:
        assert config.startswith(shlex.quote(str(companion)) + " project-hook ")
    assert " -m scrip_core " not in config


def test_project_hook_preserves_unicode_json_through_shell(tmp_path):
    parent = tmp_path / "O'Brien & café 世界"
    parent.mkdir()
    workspace, base, plan = setup(parent)
    project.start(workspace, base, session_mode=True)
    raw = payload(workspace)
    raw["conversationId"] = "session-café-世界"
    assert invoke(plan, raw)["decision"] == "auto_approve"
    assert project.status(workspace, base)["bound_session"] == raw["conversationId"]


def test_preview_and_unconfirmed_apply_have_no_side_effects(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    base = tmp_path / "state"
    plan = project.plan_setup(workspace, base, [COMMAND])
    assert list(workspace.iterdir()) == []
    assert not base.exists()
    with pytest.raises(ValueError, match="explicit approval"):
        project.apply_setup(plan, base)
    assert not base.exists()
    with pytest.raises(ValueError, match="one-time setup"):
        project.start(workspace, base)
    assert not base.exists()
    project.stop(workspace, base)
    assert not base.exists()


def test_setup_preserves_other_hooks_backs_up_and_does_not_activate(tmp_path):
    workspace, base, first = setup(tmp_path)
    original = {**json.loads(first.content), "user-hook": {"enabled": True}}
    first.target.write_text(json.dumps(original))
    second = project.plan_setup(workspace, base, [COMMAND, "git status"])
    project.apply_setup(second, base, confirmed=True)
    assert json.loads(second.target.read_text())["user-hook"] == {"enabled": True}
    assert list(second.target.parent.glob("*.scrip-backup-*"))
    assert not project.status(workspace, base)["active"]
    before = second.target.read_bytes()
    project.start(workspace, base)
    project.stop(workspace, base)
    assert second.target.read_bytes() == before  # start/stop never install or edit hooks.


def test_stale_and_user_owned_setup_refused(tmp_path):
    workspace, base, first = setup(tmp_path)
    plan = project.plan_setup(workspace, base, [COMMAND])
    first.target.write_text('{"user": true}')
    with pytest.raises(ValueError, match="changed since review"):
        project.apply_setup(plan, base, confirmed=True)
    first.target.write_text(json.dumps({project.HOOK_NAME: {"command": "user-owned"}}))
    with pytest.raises(ValueError, match="user-owned or changed"):
        project.plan_setup(workspace, base, [COMMAND])
    with pytest.raises(ValueError, match="missing or changed"):
        project.start(workspace, base)


def test_actual_hook_process_approves_only_exact_command_and_revokes_cached_hook(tmp_path):
    workspace, base, plan = setup(tmp_path)
    assert (
        invoke(plan, payload(workspace))["decision"] == "allow"
    )  # Native policy, not auto approval.
    project.start(workspace, base)
    assert invoke(plan, payload(workspace))["decision"] == "auto_approve"
    assert invoke(plan, payload(workspace))["decision"] == "allow"  # No automatic replay.
    assert (
        invoke(plan, payload(workspace, 2, CommandLine=COMMAND + "; git push"))["decision"]
        == "allow"
    )
    assert invoke(plan, payload(workspace, 3, RunPersistent=True))["decision"] == "allow"
    assert invoke(plan, payload(workspace, 4, RequestedTerminalID="other"))["decision"] == "allow"
    project.stop(workspace, base)
    assert invoke(plan, payload(workspace, 5))["decision"] == "allow"
    assert not project.status(workspace, base)["active"]
    project.start(workspace, base)
    assert invoke(plan, payload(workspace, 6))["decision"] == "auto_approve"


def test_expiry_and_old_installation_do_not_auto_approve(tmp_path, clock):
    workspace, base, first = setup(tmp_path)
    grant = project.start(workspace, base)
    state = project.project_state(base, workspace)
    service = create_service(state / "scrip.sqlite3")
    service.set_project_authorization(grant.model_copy(update={"expires_at": clock()}))
    assert invoke(first, payload(workspace))["decision"] == "allow"
    second = project.plan_setup(workspace, base, [COMMAND])
    project.apply_setup(second, base, confirmed=True)
    project.start(workspace, base)
    assert invoke(first, payload(workspace, 2))["decision"] == "allow"
    assert invoke(second, payload(workspace, 3))["decision"] == "auto_approve"


@pytest.mark.parametrize("arguments", [{"Cwd": "relative"}, {"Cwd": ""}, {"WaitMsBeforeAsync": -1}])
def test_malformed_execution_context_never_approves(tmp_path, arguments):
    workspace, base, plan = setup(tmp_path)
    project.start(workspace, base)
    assert invoke(plan, payload(workspace, **arguments))["decision"] == "force_ask"
    diagnostic = project.status(workspace, base)["last_hook"]
    assert diagnostic["error_type"] == "ValueError"
    assert diagnostic["host_response"] == "force_ask"


def test_diagnostics_keep_field_types_without_command_or_secret_values(tmp_path):
    workspace, base, plan = setup(tmp_path)
    project.start(workspace, base)
    raw = payload(workspace, CommandLine="SECRET_COMMAND", Cwd="SECRET_PATH")
    raw["transcriptPath"] = "SECRET_TRANSCRIPT"
    del raw["stepIdx"]
    assert invoke(plan, raw)["decision"] == "force_ask"
    diagnostic = project.status(workspace, base)["last_hook"]
    assert diagnostic["stage"] == "normalize"
    assert diagnostic["schema"]["step_index_type"] == "NoneType"
    assert not diagnostic["schema"]["step_index_valid"]
    assert "SECRET_" not in json.dumps(diagnostic)


def test_actual_live_cwd_and_tool_summary_shape_is_supported(tmp_path):
    workspace, base, plan = setup(tmp_path)
    project.start(workspace, base)
    raw = payload(workspace)
    raw["cwd"] = str(workspace)
    del raw["toolCall"]["args"]["Cwd"]
    raw["toolCall"]["args"]["toolSummary"] = "PRIVATE_DISPLAY_TEXT"
    assert invoke(plan, raw)["decision"] == "auto_approve"
    diagnostic = project.status(workspace, base)["last_hook"]
    assert diagnostic["stage"] == "complete"
    assert "PRIVATE_DISPLAY_TEXT" not in json.dumps(diagnostic)


def test_disagreeing_working_directories_reject_approval(tmp_path):
    workspace, base, plan = setup(tmp_path)
    project.start(workspace, base, session_mode=True)
    raw = payload(workspace)
    raw["cwd"] = str(workspace.parent)
    assert invoke(plan, raw)["decision"] == "force_ask"
    assert project.status(workspace, base)["bound_session"] is None


def test_session_mode_approves_different_commands_in_one_conversation_only(tmp_path):
    workspace, base, plan = setup(tmp_path)
    project.start(workspace, base, session_mode=True)
    assert (
        invoke(plan, payload(workspace, 1, CommandLine="first command"))["decision"]
        == "auto_approve"
    )
    assert (
        invoke(plan, payload(workspace, 2, CommandLine="different command"))["decision"]
        == "auto_approve"
    )
    other = payload(workspace, 3, CommandLine="third command")
    other["conversationId"] = "another-conversation"
    assert invoke(plan, other)["decision"] == "allow"
    bound = project.status(workspace, base)["bound_session"]
    assert bound == "real-hook-process"
    project.start(workspace, base, session_mode=True)
    assert project.status(workspace, base)["bound_session"] == bound
    project.stop(workspace, base)
    assert invoke(plan, payload(workspace, 4, CommandLine="after stop"))["decision"] == "allow"


def test_setup_without_command_list_supports_session_mode(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    base = tmp_path / "state"
    plan = project.plan_setup(workspace, base, [])
    assert not base.exists()
    project.apply_setup(plan, base, confirmed=True)
    with pytest.raises(ValueError, match="No exact commands"):
        project.start(workspace, base)
    project.start(workspace, base, session_mode=True)
    assert invoke(plan, payload(workspace))["decision"] == "auto_approve"


def test_nonobject_input_diagnostic_does_not_record_values(tmp_path):
    workspace, base, plan = setup(tmp_path)
    project.start(workspace, base)
    assert invoke(plan, ["SECRET_VALUE"])["decision"] == "force_ask"
    diagnostic = project.status(workspace, base)["last_hook"]
    assert diagnostic["schema"] == {"payload_type": "list"}
    assert "SECRET_VALUE" not in json.dumps(diagnostic)


def test_another_project_and_questions_cannot_use_shell_authorization(tmp_path):
    workspace, base, plan = setup(tmp_path)
    project.start(workspace, base)
    other = tmp_path / "other"
    other.mkdir()
    assert invoke(plan, payload(other))["decision"] == "force_ask"
    assert not project.status(other, base)["active"]
    raw = payload(workspace)
    raw["toolCall"] = {
        "name": "ask_question",
        "args": {
            "questions": [{"question": "Choose?", "options": ["A", "B"]}],
        },
    }
    response = invoke(plan, raw)
    assert response["decision"] == "force_ask"
    assert not any(key in response for key in ("answer", "overwrite", "injectSteps"))


def test_context_contains_paths_only_as_data(tmp_path):
    workspace = tmp_path / "O'Brien $env- & project"
    workspace.mkdir()
    plan = project.plan_setup(workspace, tmp_path / "state", [COMMAND])
    config = plan.record.entry["PreToolUse"][0]["hooks"][0]["command"]
    if os.name == "nt":
        script = base64.b64decode(config.split()[-1]).decode("utf-16le")
        context = script.split("'--context' '")[1].split("'")[0]
        assert str(workspace) not in script
    else:
        args = shlex.split(config)
        context = args[args.index("--context") + 1]
    assert str(workspace) not in config
    assert json.loads(base64.urlsafe_b64decode(context))["workspace"] == str(workspace)


def test_project_cli_is_available_without_qt_or_service(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scrip_core",
            "--data-dir",
            str(tmp_path / "state"),
            "status",
            "--project",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert not json.loads(result.stdout)["active"]
    assert not (tmp_path / "state").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows symlink privileges")
def test_redirected_settings_are_not_followed(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (workspace / ".agents").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink privilege unavailable")
    with pytest.raises(ValueError, match="redirected"):
        project.plan_setup(workspace, tmp_path / "state", [COMMAND])
    assert list(outside.iterdir()) == []


def test_applied_project_commands_print_one_short_confirmation(tmp_path, monkeypatch, capsys):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    base = tmp_path / "state"
    monkeypatch.chdir(workspace)

    def run(*arguments):
        monkeypatch.setattr(sys, "argv", ["scrip", "--data-dir", str(base), *arguments])
        assert cli.main() == 0
        result = capsys.readouterr()
        assert result.err == ""
        return result.out

    assert run("setup", "--allow-command", COMMAND, "--apply") == "Scrip setup complete.\n"
    assert project.status(workspace, base)["configured"]
    assert not project.status(workspace, base)["active"]
    assert run("start") == "Scrip started.\n"
    assert project.status(workspace, base)["scope"] == "conversation"
    assert run("stop") == "Scrip stopped.\n"
    assert not project.status(workspace, base)["active"]
    assert run("start", "--exact") == "Scrip started.\n"
    assert project.status(workspace, base)["scope"] == "exact"
    assert run("stop") == "Scrip stopped.\n"
    preview = run("setup")
    assert "Review Antigravity project hooks" in preview
    assert "Preview only" in preview
    status = json.loads(run("status", "--project"))
    assert not status["active"]


@pytest.mark.parametrize("arguments", [("start",), ("setup", "--apply")])
def test_failed_commands_do_not_print_success(tmp_path, monkeypatch, capsys, arguments):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    hooks = workspace / ".agents"
    hooks.mkdir()
    (hooks / "hooks.json").write_text("invalid JSON")
    monkeypatch.chdir(workspace)
    monkeypatch.setattr(sys, "argv", ["scrip", "--data-dir", str(tmp_path / "state"), *arguments])
    assert cli.main() == 1
    result = capsys.readouterr()
    assert result.out == ""
    assert result.err.startswith("Scrip: ")
