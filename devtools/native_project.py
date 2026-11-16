"""Exercise the bundled project CLI and generated hook, never a proposed tool command."""

import json
import os
import subprocess
import tempfile
from pathlib import Path


def check(executable: Path) -> None:
    executable = executable.resolve()
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    environment["PATH"] = os.pathsep.join(
        entry
        for entry in environment.get("PATH", "").split(os.pathsep)
        if not (Path(entry) / "scrip.exe").is_file()
    )
    with tempfile.TemporaryDirectory(prefix="scrip-project-package-") as directory:
        root = Path(directory).resolve()
        workspace, state = root / "O'Brien & project", root / "state"
        workspace.mkdir()
        proposed = 'git grep -n "staffPortalRoutes"'

        def cli(*arguments: str) -> str:
            result = subprocess.run(
                [str(executable), "--data-dir", str(state), *arguments],
                cwd=workspace,
                env=environment,
                text=True,
                capture_output=True,
                check=True,
                timeout=20,
            )
            assert result.stderr == "", result.stderr
            return result.stdout

        cli("setup", "--allow-command", proposed)
        assert not state.exists() and not (workspace / ".agents").exists()
        assert cli("setup", "--allow-command", proposed, "--apply") == "Scrip setup complete.\n"
        target = workspace / ".agents/hooks.json"
        before = target.read_bytes()
        entry = json.loads(before)["scrip-project-commands"]["PreToolUse"][0]["hooks"][0]
        generated = entry["command"]
        assert not json.loads(cli("status", "--project"))["active"]

        def hook(
            index: int,
            command: str,
            conversation: str = "native-project-check",
            live_shape: bool = False,
        ) -> str:
            raw = {
                "conversationId": conversation,
                "workspacePaths": [str(workspace)],
                "stepIdx": index,
                "toolCall": {
                    "name": "run_command",
                    "args": {
                        "CommandLine": command,
                        "Cwd": str(workspace),
                        "WaitMsBeforeAsync": 100,
                    },
                },
            }
            if live_shape:
                raw["cwd"] = str(workspace)
                del raw["toolCall"]["args"]["Cwd"]
                raw["toolCall"]["args"]["toolSummary"] = "Display-only test description"
            result = subprocess.run(
                f'cmd.exe /D /S /C "{generated}"',
                input=json.dumps(raw),
                cwd=workspace,
                env=environment,
                text=True,
                capture_output=True,
                check=True,
                timeout=15,
            )
            assert not result.stderr, result.stderr
            return json.loads(result.stdout)["decision"]

        assert hook(1, proposed) == "allow"
        cli("start", "--exact")
        assert json.loads(cli("status", "--project"))["active"]
        assert hook(2, proposed) == "auto_approve"
        assert hook(2, proposed) == "allow"
        assert hook(3, proposed + "; git push") == "allow"
        assert hook(4, proposed) == "auto_approve"
        assert cli("stop") == "Scrip stopped.\n"
        assert hook(5, proposed) == "allow"
        assert not json.loads(cli("status", "--project"))["active"]
        assert cli("start") == "Scrip started.\n"
        assert json.loads(cli("status", "--project"))["scope"] == "conversation"
        assert hook(6, "NEVER_EXECUTE_FIRST_SESSION_COMMAND") == "auto_approve"
        assert hook(7, "NEVER_EXECUTE_DIFFERENT_SESSION_COMMAND", live_shape=True) == "auto_approve"
        assert hook(8, "NEVER_EXECUTE_OTHER_CONVERSATION", conversation="other") == "allow"
        cli("start")  # Starting again must not silently unbind a conversation.
        assert json.loads(cli("status", "--project"))["bound_session"] == "native-project-check"
        assert cli("stop") == "Scrip stopped.\n"
        assert hook(9, "NEVER_EXECUTE_AFTER_STOP") == "allow"
        assert target.read_bytes() == before
    print(
        "Bundled project CLI with Scrip absent from PATH passed: preview, explicit setup, "
        "start/stop, exact commands, replay, and generated hooks through Command Prompt. "
        "No proposed command executed."
    )
