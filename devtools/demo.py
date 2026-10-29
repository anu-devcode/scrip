"""Isolated protocol demonstration; no model, IDE, or proposed command execution."""

import tempfile
from pathlib import Path

from scrip_core.models import Rule
from scrip_core.notifications import ConsoleSink

from .process import invoke_hook, running_service


def main() -> None:
    with (
        tempfile.TemporaryDirectory(prefix="scrip-demo-") as temporary,
        running_service(Path(temporary).resolve()) as local,
    ):
        payload = {
            "conversationId": "demonstration",
            "workspacePaths": [str(local.workspace)],
            "stepIdx": 0,
            "toolCall": {"name": "run_command", "args": {"CommandLine": "npm test"}},
        }

        def decision() -> str:
            return str(invoke_hook(local.settings, "antigravity", payload)["decision"])

        print(f"1. Unknown action: {decision()}")
        local.companion.put_rule(
            Rule(
                id="demo-task",
                adapter="antigravity",
                workspace=str(local.workspace),
                tool="run_command",
                arguments={"CommandLine": "npm test"},
                action="allow",
            )
        )
        payload["stepIdx"] = 1
        print(f"2. Fresh action matching an explicit rule: {decision()}")
        print(f"3. Replaying that approval: {decision()}")
        payload["stepIdx"] = 2
        payload["toolCall"] = {
            "name": "ask_question",
            "args": {
                "questions": [{"question": "Which database?", "options": ["SQLite", "PostgreSQL"]}]
            },
        }
        print(f"4. Question: {decision()} (native question flow; no answer supplied)")
        inbox = local.client.request("/v1/inbox")["items"]
        print(f"5. Pending input requests: {sum(item['kind'] == 'input' for item in inbox)}")
        local.companion.deliver_notifications(ConsoleSink())
    print("Demo complete. Temporary service and state removed.")


if __name__ == "__main__":
    main()
