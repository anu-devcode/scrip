"""Reviewed project setup and daemon-free exact command approval toggles."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shlex
import subprocess
import sys
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from pydantic import Field

from .adapters import antigravity
from .adapters.common import JsonObject, cli_launcher
from .authorization import ProjectAuthorization, SessionCommandScope
from .bootstrap import create_service
from .connections import atomic_settings
from .limits import MAX_EVENT_BYTES
from .models import Contract, Rule, Tool, ToolRequested, utc_now, workspace_path
from .settings import private_write

HOOK_NAME = "scrip-project-commands"


class SetupRecord(Contract):
    installation_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    workspace: str
    commands: tuple[str, ...] = Field(default=(), max_length=100)
    entry: JsonObject


@dataclass(frozen=True)
class SetupPlan:
    target: Path
    previous: bytes | None
    content: str
    record: SetupRecord


def project_state(base: Path, workspace: Path) -> Path:
    identity = os.path.normcase(str(workspace.resolve()))
    return base / "projects" / hashlib.sha256(identity.encode()).hexdigest()


def hook_path(workspace: Path) -> Path:
    if not workspace.is_absolute() or not workspace.is_dir():
        raise ValueError("Choose an existing local project directory")
    folder = workspace / ".agents"
    target = folder / "hooks.json"
    if any(path.is_symlink() or path.is_junction() for path in (folder, target)):
        raise ValueError("Refusing to edit symlinked or redirected project hooks")
    if folder.exists() and not folder.is_dir():
        raise ValueError("The project .agents path is not a directory")
    return target


def read_hooks(target: Path) -> tuple[bytes | None, JsonObject]:
    raw = target.read_bytes() if target.exists() else None
    if raw is not None and len(raw) > 1024 * 1024:
        raise ValueError("Project hooks file is too large to edit safely")
    document = json.loads(raw.decode("utf-8-sig")) if raw is not None else {}
    if not isinstance(document, dict):
        raise ValueError("Antigravity hooks.json must contain an object")
    return raw, document


def record_for(state: Path, workspace: Path) -> SetupRecord:
    path = state / "setup.json"
    if not path.is_file():
        raise ValueError("Review one-time setup first: scrip setup")
    record = SetupRecord.model_validate_json(path.read_text(encoding="utf-8"))
    if record.workspace != str(workspace):
        raise ValueError("Saved setup belongs to a different workspace")
    return record


def plan_setup(workspace: Path, base: Path, commands: list[str]) -> SetupPlan:
    """Preview only: never creates directories, authorization, or host configuration."""
    workspace = workspace.resolve()
    target = hook_path(workspace)
    state = project_state(base.resolve(), workspace)
    if any(not item.strip() or "\x00" in item for item in commands):
        raise ValueError("An exact --allow-command cannot be empty")
    previous, document = read_hooks(target)
    old = record_for(state, workspace) if (state / "setup.json").exists() else None
    if HOOK_NAME in document and (old is None or document[HOOK_NAME] != old.entry):
        raise ValueError("Scrip hook is user-owned or changed; it will not be overwritten")
    installation = uuid4().hex
    context = base64.urlsafe_b64encode(
        json.dumps(
            {
                "workspace": str(workspace),
                "state": str(state),
            }
        ).encode()
    ).decode()
    # Resolve the actual runtime at setup time so an existing host process can
    # invoke this hook even when it inherited PATH before Scrip was installed.
    arguments = [
        *cli_launcher(),
        "project-hook",
        "--context",
        context,
        "--installation-id",
        installation,
    ]
    command_line = (
        f'"{arguments[0]}" {subprocess.list2cmdline(arguments[1:])}'
        if os.name == "nt"
        else shlex.join(arguments)
    )
    entry = {
        "enabled": True,
        "PreToolUse": [
            {
                "matcher": "^run_command$",
                "hooks": [
                    {
                        "type": "command",
                        "timeout": 5,
                        "command": command_line,
                    }
                ],
            }
        ],
    }
    record = SetupRecord(
        installation_id=installation,
        workspace=str(workspace),
        commands=tuple(dict.fromkeys(commands)),
        entry=entry,
    )
    document[HOOK_NAME] = entry
    return SetupPlan(target, previous, json.dumps(document, indent=2) + "\n", record)


def apply_setup(plan: SetupPlan, base: Path, *, confirmed: bool = False) -> None:
    """Write only after the user's explicit `scrip setup --apply` invocation."""
    if not confirmed:
        raise ValueError("Setup requires explicit approval: repeat with --apply")
    workspace = Path(plan.record.workspace)
    target = hook_path(workspace)
    previous, _ = read_hooks(target)
    if target != plan.target or previous != plan.previous:
        raise ValueError("Hooks changed since review; review setup again")
    state = project_state(base.resolve(), workspace)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    service = create_service(state / "scrip.sqlite3")
    service.set_project_authorization(None)
    target.parent.mkdir(exist_ok=True)
    if previous is not None:
        private_write(
            target.with_name(f"hooks.json.scrip-backup-{uuid4().hex}"), previous.decode("utf-8-sig")
        )
    # Persist ownership before touching host configuration, for recovery after a crash.
    atomic_settings(state / "setup.json", plan.record.model_dump_json(indent=2) + "\n")
    current = target.read_bytes() if target.exists() else None
    if current != previous:
        raise ValueError("Hooks changed during setup; no approvals are active")
    atomic_settings(target, plan.content)


def start(workspace: Path, base: Path, *, session_mode: bool = False) -> ProjectAuthorization:
    """Activate explicit command scope; never installs or edits host hooks."""
    workspace = workspace.resolve()
    state = project_state(base.resolve(), workspace)
    record = record_for(state, workspace)
    if not session_mode and not record.commands:
        raise ValueError("No exact commands configured; use scrip start for conversation scope")
    _, document = read_hooks(hook_path(workspace))
    if document.get(HOOK_NAME) != record.entry:
        raise ValueError("Project hook is missing or changed; review scrip setup again")
    service = create_service(state / "scrip.sqlite3")
    authorization = ProjectAuthorization(
        id=record.installation_id,
        expires_at=utc_now() + timedelta(hours=24),
        session=SessionCommandScope(
            adapter="antigravity", workspace=str(workspace), tool="run_command"
        )
        if session_mode
        else None,
        rules=()
        if session_mode
        else tuple(
            Rule(
                id=f"project-{index}",
                adapter="antigravity",
                workspace=str(workspace),
                tool="run_command",
                arguments={"CommandLine": command, "Cwd": str(workspace)},
                action="allow",
            )
            for index, command in enumerate(record.commands)
        ),
    )
    return service.activate_project_authorization(authorization)


def stop(workspace: Path, base: Path) -> None:
    database = project_state(base.resolve(), workspace.resolve()) / "scrip.sqlite3"
    if database.is_file():
        create_service(database).set_project_authorization(None)


def status(workspace: Path, base: Path) -> JsonObject:
    workspace = workspace.resolve()
    state = project_state(base.resolve(), workspace)
    database = state / "scrip.sqlite3"
    authorization = create_service(database).project_authorization() if database.is_file() else None
    diagnostic = state / "last-hook.json"
    return {
        "workspace": str(workspace),
        "configured": (state / "setup.json").is_file(),
        "active": authorization is not None and authorization.expires_at > utc_now(),
        "expires_at": authorization.expires_at.isoformat() if authorization else None,
        "scope": "conversation" if authorization and authorization.session else "exact",
        "bound_session": authorization.session.session_id
        if authorization and authorization.session
        else None,
        "commands": [rule.arguments["CommandLine"] for rule in authorization.rules]
        if authorization
        else [],
        "live_host_validation": "unverified",
        "last_hook": json.loads(diagnostic.read_text(encoding="utf-8"))
        if diagnostic.is_file()
        else None,
    }


def canonical_command(event: ToolRequested) -> ToolRequested:
    arguments = dict(event.payload.arguments)
    command = arguments.get("CommandLine")
    cwd = arguments.get("Cwd")
    if not isinstance(command, str) or not command or not isinstance(cwd, str) or not cwd:
        raise ValueError("CommandLine and absolute Cwd are required")
    arguments["Cwd"] = workspace_path(cwd)
    # Only discard the documented output-wait interval and an explicitly false
    # persistent flag. Unknown execution options remain part of exact matching.
    wait = arguments.pop("WaitMsBeforeAsync", None)
    if wait is not None and (type(wait) is not int or wait < 0):
        raise ValueError("Invalid command wait interval")
    if arguments.get("RunPersistent") is False:
        del arguments["RunPersistent"]
    summary = arguments.pop("toolSummary", None)
    if summary is not None and not isinstance(summary, str):
        raise ValueError("Invalid display-only toolSummary")
    return event.model_copy(update={"payload": Tool(name=event.payload.name, arguments=arguments)})


def payload_shape(payload: object) -> JsonObject:
    """Record callback field types only; omit command, path, and argument values."""
    if not isinstance(payload, dict):
        return {"payload_type": type(payload).__name__}
    call = payload.get("toolCall")
    arguments = call.get("args") if isinstance(call, dict) else None
    roots = payload.get("workspacePaths")
    index = payload.get("stepIdx")
    return {
        "top_level_keys": [str(key)[:80] for key in list(payload)[:30]],
        "conversation_id_type": type(payload.get("conversationId")).__name__,
        "workspace_paths_type": type(roots).__name__,
        "workspace_count": len(roots) if isinstance(roots, list) else None,
        "step_index_type": type(index).__name__,
        "step_index_valid": type(index) is int and index >= 0,
        "tool_call_type": type(call).__name__,
        "tool_call_keys": list(call)[:20] if isinstance(call, dict) else [],
        "tool_is_run_command": call.get("name") == "run_command"
        if isinstance(call, dict)
        else False,
        "arguments_type": type(arguments).__name__,
        "argument_keys": list(arguments)[:30] if isinstance(arguments, dict) else [],
        "command_type": type(arguments.get("CommandLine")).__name__
        if isinstance(arguments, dict)
        else None,
        "cwd_type": type(arguments.get("Cwd")).__name__ if isinstance(arguments, dict) else None,
        "top_level_cwd_type": type(payload.get("cwd")).__name__,
    }


def run_project_hook(context: str, installation: str) -> int:
    response = {
        "decision": "allow",
        "reason": "Scrip grants no approval; native host policy applies",
    }
    state: Path | None = None
    diagnostic: JsonObject = {"at": utc_now().isoformat(), "stage": "context"}
    try:
        decoded = json.loads(base64.urlsafe_b64decode(context).decode())
        workspace, state = Path(decoded["workspace"]), Path(decoded["state"])
        if not workspace.is_absolute() or not state.is_absolute():
            raise ValueError("Invalid project context")
        database = state / "scrip.sqlite3"
        diagnostic["stage"] = "authorization"
        if database.is_file():
            service = create_service(database)
            authorization = service.project_authorization()
            if (
                authorization is not None
                and authorization.id == installation
                and authorization.expires_at > utc_now()
            ):
                diagnostic["stage"] = "input"
                raw = sys.stdin.buffer.read(MAX_EVENT_BYTES + 1)
                diagnostic["input_bytes"] = len(raw)
                if len(raw) > MAX_EVENT_BYTES:
                    raise ValueError("Hook payload is too large")
                diagnostic["stage"] = "decode"
                payload = json.loads(raw.decode("utf-8-sig"))
                diagnostic["schema"] = payload_shape(payload)
                diagnostic["stage"] = "normalize"
                payload = command_context(payload)
                event = antigravity.normalize("PreToolUse", payload, "enforce")
                if not isinstance(event, ToolRequested) or event.payload.name != "run_command":
                    raise ValueError("This hook authorizes only shell commands")
                if Path(event.workspace) != workspace.resolve():
                    raise ValueError("Workspace differs from the configured project")
                diagnostic["stage"] = "policy"
                result = service.ingest(canonical_command(event), authorization_id=installation)
                diagnostic["policy_decision"] = result.decision.action
                diagnostic["stage"] = "complete"
                if result.decision.action in ("allow", "deny"):
                    response = antigravity.hook_response(
                        "PreToolUse", event, result.decision, "enforce"
                    )
                # Unknown commands, expired grants, and retries delegate to the host.
                # They never force a prompt over a user's existing native permission.
    except Exception as error:
        diagnostic["error_type"] = type(error).__name__
        print(
            f"Scrip hook unavailable ({type(error).__name__}); review in Antigravity",
            file=sys.stderr,
        )
        response = antigravity.unavailable_response("PreToolUse", "enforce")
    finally:
        diagnostic["host_response"] = response["decision"]
        if state is not None and state.is_dir():
            with suppress(OSError):
                atomic_settings(state / "last-hook.json", json.dumps(diagnostic, indent=2))
    print(json.dumps(response, ensure_ascii=False, allow_nan=False))
    return 0


def command_context(payload: object) -> JsonObject:
    """Validate the actual host's top-level cwd without guessing a missing directory."""
    if not isinstance(payload, dict):
        raise ValueError("Hook payload must be an object")
    result = dict(payload)
    call = result.get("toolCall")
    if isinstance(call, dict) and isinstance(call.get("args"), dict):
        arguments = dict(call["args"])
        native_cwd, top_cwd = arguments.get("Cwd"), result.get("cwd")
        if top_cwd is not None:
            if not isinstance(top_cwd, str):
                raise ValueError("Invalid top-level cwd")
            top_cwd = workspace_path(top_cwd)
            if native_cwd is not None:
                if not isinstance(native_cwd, str) or workspace_path(native_cwd) != top_cwd:
                    raise ValueError("Callback working directories disagree")
            else:
                arguments["Cwd"] = top_cwd
        result["toolCall"] = {**call, "args": arguments}
    return result


def command(args: argparse.Namespace) -> None:
    workspace, base = Path.cwd().resolve(), Path(args.data_dir).resolve()
    if args.command == "setup":
        plan = plan_setup(workspace, base, args.allow_command)
        if args.apply:
            apply_setup(plan, base, confirmed=True)
            print("Scrip setup complete.")
        else:
            print(f"Review Antigravity project hooks: {plan.target}\n{plan.content}")
            if plan.record.commands:
                print("Exact commands:")
                for item in plan.record.commands:
                    print(f"  {item}")
            print("Preview only. To approve this setup, repeat the command with --apply.")
    elif args.command == "start":
        start(workspace, base, session_mode=not args.exact)
        print("Scrip started.")
    else:
        stop(workspace, base)
        print("Scrip stopped.")
