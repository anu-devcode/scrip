"""Claude Code's documented hook contract: https://code.claude.com/docs/en/hooks."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

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

HOOKS: tuple[str, ...] = ("SessionStart", "PreToolUse", "PostToolUse", "Stop", "SessionEnd")
CAPABILITIES = AdapterCapabilities(
    adapter="claude-code",
    interface="documented settings.json hooks with JSON stdin/stdout",
    workspace_scope="fixed-cwd sessions; directory changes require host review",
)
QUESTION_FORMAT = QuestionFormat("label", "multiSelect")


def normalize(hook: str, payload: JsonObject, mode: HookMode = "observe") -> Event:
    if hook not in HOOKS or not isinstance(payload, dict):
        raise ValueError("Unsupported Claude Code hook or payload")
    if payload.get("hook_event_name", hook) != hook:
        raise ValueError("Payload hook_event_name does not match the invoked hook")
    session = require_text(payload.get("session_id"), "session_id")
    workspace = workspace_path(require_text(payload.get("cwd"), "cwd"))
    operation_id = ""
    if hook in ("PreToolUse", "PostToolUse"):
        tool_id = require_text(payload.get("tool_use_id"), "tool_use_id")
        identity = json.dumps(["claude-code", session, workspace, tool_id])
        operation_id = hashed_id("ccop_", identity)
        identity += "/" + hook
    else:
        identity = json.dumps([session, workspace, hook, str(uuid.uuid4())])
    context: EventContext = {
        "adapter": "claude-code",
        "session_id": session,
        "workspace": workspace,
        "event_id": hashed_id("cc_", identity),
    }
    if hook == "SessionStart":
        return SessionEvent(**context, kind="session.started")
    if hook == "SessionEnd":
        return SessionEvent(
            **context, kind="session.completed", payload=SessionInfo(reason=payload.get("reason"))
        )
    if hook == "Stop":
        background = payload.get("background_tasks") or payload.get("session_crons")
        return SessionEvent(**context, kind="session.progress" if background else "turn.completed")
    name = require_text(payload.get("tool_name"), "tool_name")
    arguments = payload.get("tool_input")
    if not isinstance(arguments, dict):
        raise ValueError("Missing tool_input")
    if hook == "PostToolUse":
        return ToolCompleted(
            **context,
            kind="tool.completed",
            operation_id=operation_id,
            payload=ToolResult(name=name, arguments=arguments),
        )
    if name == "AskUserQuestion":
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
    if hook != "PreToolUse" or isinstance(event, InputRequested) or mode == "observe":
        return {}
    if decision.action not in ("allow", "deny", "ask"):
        raise ValueError("Invalid Claude Code policy response")
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision.action,
            "permissionDecisionReason": decision.reason,
        }
    }


def unavailable_response(hook: str, mode: HookMode = "observe") -> JsonObject:
    if hook != "PreToolUse" or mode == "observe":
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": "Scrip unavailable; review this action",
        }
    }


def hook_configuration(data_dir: Path, mode: HookMode = "observe") -> JsonObject:
    hooks: JsonObject = {}
    for hook in HOOKS:
        entry: JsonObject = {"hooks": [hook_handler("claude-code", hook, data_dir, mode)]}
        if hook in ("PreToolUse", "PostToolUse"):
            entry["matcher"] = ".*"
        hooks[hook] = [entry]
    return {"hooks": hooks}
