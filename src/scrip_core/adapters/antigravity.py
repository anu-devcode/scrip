"""Antigravity's documented hook contract: https://antigravity.google/docs/hooks."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Literal

from ..models import (
    Decision,
    Event,
    Input,
    InputRequested,
    SessionEvent,
    SessionInfo,
    Tool,
    ToolCompleted,
    ToolRequested,
    ToolResult,
    workspace_path,
)
from .common import (
    AdapterCapabilities,
    EventContext,
    HookMode,
    JsonObject,
    QuestionFormat,
    hashed_id,
    hook_handler,
    normalize_questions,
    require_text,
)

HOOKS: tuple[str, ...] = ("SessionStart", "PreToolUse", "PostToolUse", "Stop")
CAPABILITIES = AdapterCapabilities(
    adapter="antigravity",
    interface="documented hooks.json with JSON stdin/stdout",
    workspace_scope="single-root sessions; multi-root payloads require host review",
)
QUESTION_FORMAT = QuestionFormat("text", "is_multi_select", string_options=True)


def normalize(hook: str, payload: JsonObject, mode: HookMode = "observe") -> Event:
    if hook not in HOOKS or not isinstance(payload, dict):
        raise ValueError("Unsupported Antigravity hook or payload")
    session = require_text(payload.get("conversationId"), "conversationId")
    workspaces = payload.get("workspacePaths")
    if not isinstance(workspaces, list) or not workspaces:
        raise ValueError("Missing workspacePaths")
    roots = [workspace_path(require_text(root, "workspacePaths")) for root in workspaces]
    if len(roots) != 1:
        raise ValueError("Multi-root session routing is not supported by this adapter yet")
    workspace = roots[0]
    call = payload.get("toolCall", {})
    if not isinstance(call, dict) or not isinstance(call.get("args", {}), dict):
        raise ValueError("Invalid toolCall or tool arguments")
    arguments: JsonObject = call.get("args", {})
    if arguments.get("Cwd") is not None:
        candidate = workspace_path(require_text(arguments["Cwd"], "Cwd"))
        if not Path(candidate).is_relative_to(Path(workspace)):
            raise ValueError("Tool working directory is outside the reported workspaces")
    operation_id = ""
    if hook in ("PreToolUse", "PostToolUse"):
        index = payload.get("stepIdx")
        if type(index) is not int or index < 0:
            raise ValueError("Tool events require a non-negative stepIdx")
        suffix = f"{hook}/{index}"
        operation_id = hashed_id("agop_", json.dumps(["antigravity", session, workspace, index]))
    elif hook == "Stop":
        execution = payload.get("executionNum")
        if type(execution) is not int or execution < 0:
            raise ValueError("Stop requires a non-negative executionNum")
        suffix = f"Stop/{execution}/{payload.get('fullyIdle')}"
    else:
        suffix = f"SessionStart/{uuid.uuid4()}"
    context: EventContext = {
        "adapter": "antigravity",
        "session_id": session,
        "workspace": workspace,
        "event_id": hashed_id(
            "ag_",
            json.dumps(
                ["antigravity", session, workspace, suffix],
                separators=(",", ":"),
            ),
        ),
    }
    if hook == "SessionStart":
        return SessionEvent(
            **context,
            kind="session.started",
            payload=SessionInfo(model_name=payload.get("modelName")),
        )
    if hook == "Stop":
        if type(payload.get("fullyIdle")) is not bool:
            raise ValueError("Stop requires fullyIdle")
        error = payload.get("error")
        kind: Literal["session.progress", "turn.failed", "turn.completed"] = (
            "session.progress"
            if not payload["fullyIdle"]
            else "turn.failed"
            if error
            else "turn.completed"
        )
        return SessionEvent(
            **context,
            kind=kind,
            payload=SessionInfo(
                model_name=payload.get("modelName"),
                reason=error or payload.get("terminationReason"),
            ),
        )
    name = require_text(call.get("name"), "toolCall.name")
    if hook == "PostToolUse":
        return ToolCompleted(
            **context,
            kind="tool.completed",
            operation_id=operation_id,
            payload=ToolResult(name=name, arguments=arguments, error=payload.get("error") or None),
        )
    if name == "ask_question":
        return InputRequested(
            **context,
            kind="input.requested",
            operation_id=operation_id,
            payload=Input(
                source_tool=name,
                questions=normalize_questions(
                    arguments.get("questions"),
                    QUESTION_FORMAT,
                ),
            ),
        )
    return ToolRequested(
        **context,
        kind="tool.requested",
        operation_id=operation_id,
        policy_mode=mode,
        payload=Tool(name=name, arguments=arguments),
    )


def hook_response(hook: str, event: Event, decision: Decision, mode: HookMode) -> JsonObject:
    if hook != "PreToolUse":
        return {}
    if isinstance(event, InputRequested):
        return {"decision": "allow", "reason": "Answer this question in Antigravity"}
    if mode == "observe":
        return {
            "decision": "allow",
            "reason": "Scrip is observing; host permissions remain in charge",
        }
    action = {"allow": "auto_approve", "deny": "deny", "ask": "force_ask"}.get(decision.action)
    if action is None:
        raise ValueError("Invalid decision for an execution request")
    return {"decision": action, "reason": decision.reason}


def unavailable_response(hook: str, mode: HookMode = "observe") -> JsonObject:
    if hook != "PreToolUse":
        return {}
    if mode == "observe":
        return {
            "decision": "allow",
            "reason": "Scrip observer unavailable; host policy remains in charge",
        }
    return {
        "decision": "force_ask",
        "reason": "Scrip unavailable; review this action in Antigravity",
    }


def hook_configuration(data_dir: Path, mode: HookMode = "observe") -> JsonObject:
    configuration: JsonObject = {"enabled": True}
    for hook in HOOKS:
        handler = hook_handler("antigravity", hook, data_dir, mode)
        configuration[hook] = (
            [{"matcher": ".*", "hooks": [handler]}]
            if hook in ("PreToolUse", "PostToolUse")
            else [handler]
        )
    return {"scrip-companion": configuration}
