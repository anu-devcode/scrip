"""Cursor desktop's documented hooks: https://cursor.com/docs/hooks.

Permission decisions use shell/MCP hooks only. Cursor does not enforce ask on
preToolUse, so that hook is deliberately not installed by this adapter.
"""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
from typing import Literal

from ..models import (
    Decision,
    Event,
    SessionEvent,
    SessionInfo,
    Tool,
    ToolCompleted,
    ToolRequested,
    ToolResult,
    canonical_json,
    workspace_path,
)
from .common import (
    AdapterCapabilities,
    EventContext,
    HookMode,
    JsonObject,
    hashed_id,
    hook_argv,
    require_text,
)

OBSERVATION_HOOKS = ("sessionStart", "sessionEnd", "postToolUse", "stop")
PERMISSION_HOOKS = ("beforeShellExecution", "beforeMCPExecution")
EXECUTION_HOOKS = (*PERMISSION_HOOKS, "afterShellExecution", "afterMCPExecution")
HOOKS: tuple[str, ...] = (*OBSERVATION_HOOKS, *EXECUTION_HOOKS)
CAPABILITIES = AdapterCapabilities(
    adapter="cursor",
    interface="documented desktop hooks; shell/MCP permissions, completed-tool visibility",
    workspace_scope="single-root local desktop; Scrip and hooks must run on the same machine",
    structured_questions=False,
)


def powershell_command(arguments: list[str]) -> str:
    """Cursor uses PowerShell on Windows; every argument must stay a literal string."""
    return "& " + " ".join("'" + argument.replace("'", "''") + "'" for argument in arguments)


def _context(hook: str, payload: JsonObject) -> tuple[EventContext, str]:
    if hook not in HOOKS or not isinstance(payload, dict):
        raise ValueError("Unsupported Cursor hook or payload")
    if payload.get("hook_event_name", hook) != hook:
        raise ValueError("Payload hook_event_name does not match the invoked hook")
    if os.environ.get("CURSOR_CODE_REMOTE") == "true":
        raise ValueError("Remote Cursor workspaces require a separate supported transport")
    session = require_text(payload.get("conversation_id"), "conversation_id")
    if payload.get("session_id", session) != session:
        raise ValueError("Cursor session identifiers disagree")
    roots = payload.get("workspace_roots")
    if not isinstance(roots, list) or len(roots) != 1:
        raise ValueError("Cursor connections currently require one workspace root")
    workspace = workspace_path(require_text(roots[0], "workspace_roots"))
    generation = (
        ""
        if hook in ("sessionStart", "sessionEnd")
        else require_text(payload.get("generation_id"), "generation_id")
    )
    return {
        "adapter": "cursor",
        "session_id": session,
        "workspace": workspace,
        "event_id": "",
    }, generation


def normalize(hook: str, payload: JsonObject, mode: HookMode = "observe") -> Event:
    context, generation = _context(hook, payload)
    identity: list[object] = ["cursor", context["session_id"], context["workspace"]]
    if hook in ("sessionStart", "sessionEnd", "stop"):
        kind: Literal[
            "session.started",
            "session.completed",
            "session.failed",
            "turn.completed",
            "turn.failed",
        ]
        identity += [hook, generation]
        if hook == "stop":
            status = payload.get("status")
            count = payload.get("loop_count")
            if (
                status not in ("completed", "aborted", "error")
                or type(count) is not int
                or count < 0
            ):
                raise ValueError("Cursor stop requires status and a non-negative loop_count")
            identity += [status, count]
            kind = "turn.completed" if status == "completed" else "turn.failed"
        elif hook == "sessionEnd":
            reason = require_text(payload.get("reason"), "reason")
            if reason not in ("completed", "aborted", "error", "window_close", "user_close"):
                raise ValueError("Unsupported Cursor session end reason")
            identity.append(reason)
            kind = "session.failed" if reason == "error" else "session.completed"
        else:
            kind = "session.started"
        context["event_id"] = hashed_id("cu_", canonical_json(identity))
        return SessionEvent(
            **context,
            kind=kind,
            payload=SessionInfo(model_name=payload.get("model_id") or payload.get("model")),
        )
    if hook == "postToolUse":
        name = require_text(payload.get("tool_name"), "tool_name")
        arguments = payload.get("tool_input")
        if not isinstance(arguments, dict):
            raise ValueError("Missing tool_input")
        operation = [
            *identity,
            generation,
            "tool",
            require_text(payload.get("tool_use_id"), "tool_use_id"),
        ]
    elif hook in ("beforeShellExecution", "afterShellExecution"):
        command = require_text(payload.get("command"), "command")
        sandbox = payload.get("sandbox")
        if type(sandbox) is not bool:
            raise ValueError("Shell hooks require an explicit sandbox flag")
        cwd = workspace_path(
            require_text(
                payload.get("cwd")
                if hook == "beforeShellExecution"
                else payload.get("cwd", context["workspace"]),
                "cwd",
            )
        )
        if not Path(cwd).is_relative_to(Path(context["workspace"])):
            raise ValueError("Shell directory is outside the connected workspace")
        name, arguments = "Shell", {"command": command, "cwd": cwd, "sandbox": sandbox}
        # These hooks have no documented per-call ID. An identical command in the same
        # generation shares one approval scope; repeats fall back to native review.
        operation = [*identity, generation, "shell", command]
    else:
        server = require_text(payload.get("mcp_server_name"), "mcp_server_name")
        tool = require_text(payload.get("tool_name"), "tool_name")
        parameters = json.loads(require_text(payload.get("tool_input"), "tool_input"))
        if not isinstance(parameters, dict):
            raise ValueError("MCP parameters must be a JSON object")
        endpoint = payload.get("mcp_server_url") or payload.get("url")
        launch = payload.get("command")
        if hook == "beforeMCPExecution" and not (endpoint or launch):
            raise ValueError(
                "MCP permission requests require the server endpoint or launch command"
            )
        if (
            payload.get("url")
            and payload.get("mcp_server_url")
            and payload["url"] != payload["mcp_server_url"]
        ):
            raise ValueError("MCP endpoint fields disagree")
        name = "MCP"
        arguments = {"server": server, "tool": tool, "input": parameters}
        if endpoint:
            arguments["endpoint"] = require_text(endpoint, "MCP endpoint")
        if launch:
            arguments["launch"] = require_text(launch, "MCP launch command")
        operation = [*identity, generation, "mcp", server, tool, parameters]
    operation_id = hashed_id("cuop_", canonical_json(operation))
    context["event_id"] = hashed_id("cu_", canonical_json([operation, hook]))
    if hook in PERMISSION_HOOKS:
        return ToolRequested(
            **context,
            kind="tool.requested",
            operation_id=operation_id,
            policy_mode=mode,
            payload=Tool(name=name, arguments=arguments),
        )
    # Tool output, transcripts, emails, and reasoning are deliberately not retained.
    return ToolCompleted(
        **context,
        kind="tool.completed",
        operation_id=operation_id,
        payload=ToolResult(name=name, arguments=arguments),
    )


def hook_response(hook: str, event: Event, decision: Decision, mode: HookMode) -> JsonObject:
    if hook not in PERMISSION_HOOKS:
        return {}
    action = decision.action if mode == "enforce" else "ask"
    if action not in ("allow", "deny", "ask"):
        raise ValueError("Invalid Cursor permission decision")
    return {"permission": action, "user_message": decision.reason}


def unavailable_response(hook: str, mode: HookMode = "observe") -> JsonObject:
    return (
        {"permission": "ask", "user_message": "Scrip unavailable; review this action in Cursor"}
        if hook in PERMISSION_HOOKS
        else {}
    )


def hook_configuration(data_dir: Path, mode: HookMode = "observe") -> JsonObject:
    hooks: JsonObject = {}
    for hook in OBSERVATION_HOOKS + (EXECUTION_HOOKS if mode == "enforce" else ()):
        arguments = hook_argv("cursor", hook, data_dir, mode)
        handler: JsonObject = {
            "command": powershell_command(arguments) if os.name == "nt" else shlex.join(arguments),
            "timeout": 5,
        }
        if hook in PERMISSION_HOOKS:
            handler["failClosed"] = True
        if hook == "postToolUse" and mode == "enforce":
            handler["matcher"] = r"^(?!Shell$|MCP:).+"
        hooks[hook] = [handler]
    return {"version": 1, "hooks": hooks}
