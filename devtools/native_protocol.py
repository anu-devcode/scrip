"""Check the frozen hook executable with isolated fixtures, never executing proposed tools."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from scrip_core.models import Rule

from .process import running_service


def check(executable: Path) -> None:
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    with tempfile.TemporaryDirectory(prefix="scrip-native-protocol-") as directory:
        root = Path(directory).resolve()
        with running_service(root) as service:
            settings, client, store, workspace = (
                service.settings,
                service.client,
                service.companion,
                service.workspace,
            )
            result = subprocess.run(
                [
                    str(executable),
                    "--data-dir",
                    str(settings.data_dir),
                    "adapter",
                    "config",
                    "--adapter",
                    "claude-code",
                    "--mode",
                    "enforce",
                ],
                cwd=root,
                env=environment,
                text=True,
                capture_output=True,
                check=True,
                timeout=20,
            )
            config = json.loads(result.stdout)["hooks"]

            def invoke(hook, payload):
                handler = config[hook][0]["hooks"][0]
                assert Path(handler["command"]).samefile(executable)
                completed = subprocess.run(
                    [handler["command"], *handler["args"]],
                    input=json.dumps(payload),
                    cwd=root,
                    env=environment,
                    text=True,
                    capture_output=True,
                    check=True,
                    timeout=15,
                )
                assert completed.stderr == "", completed.stderr
                return json.loads(completed.stdout)

            identity = {"session_id": "package-check", "cwd": str(workspace)}
            assert invoke("SessionStart", identity) == {}
            payload = {
                **identity,
                "tool_use_id": "first",
                "tool_name": "Read",
                "tool_input": {"file_path": str(root / "not-executed.txt")},
            }
            assert (
                invoke("PreToolUse", payload)["hookSpecificOutput"]["permissionDecision"] == "ask"
            )
            store.put_rule(
                Rule(
                    id="package-rule",
                    adapter="claude-code",
                    workspace=str(workspace),
                    tool="Read",
                    arguments=payload["tool_input"],
                    action="allow",
                )
            )
            payload["tool_use_id"] = "second"
            assert (
                invoke("PreToolUse", payload)["hookSpecificOutput"]["permissionDecision"] == "allow"
            )
            assert (
                invoke("PreToolUse", payload)["hookSpecificOutput"]["permissionDecision"] == "ask"
            )
            question = {
                **identity,
                "tool_use_id": "question",
                "tool_name": "AskUserQuestion",
                "tool_input": {"questions": [{"question": "Package check?", "options": []}]},
            }
            assert invoke("PreToolUse", question) == {}
            assert any(item["kind"] == "input" for item in client.request("/v1/inbox")["items"])
            assert invoke("PostToolUse", question) == {}
            assert not any(item["kind"] == "input" for item in client.request("/v1/inbox")["items"])
    print("Frozen hooks passed: session, exact rules, replay, questions, and resolution.")
