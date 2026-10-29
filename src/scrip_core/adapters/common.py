"""Shared adapter mechanics; native permission semantics stay in each host module."""

import hashlib
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol, TypedDict

from ..models import Contract, Decision, Event, Question

JsonObject = dict[str, Any]
HookMode = Literal["observe", "enforce"]


class EventContext(TypedDict):
    adapter: str
    session_id: str
    workspace: str
    event_id: str


class AdapterCapabilities(Contract):
    adapter: str
    interface: str
    workspace_scope: str
    validation: str = "fixture-and-local-transport-tested; live-host-unverified"
    tool_events: bool = True
    policy_decisions: bool = True
    structured_questions: bool = True
    notification_delivery: str = "durable-outbox; console or optional Qt desktop consumer"
    answer_forwarding: bool = False
    session_resume: bool = False
    plain_text_question_detection: bool = False


class HookAdapter(Protocol):
    HOOKS: tuple[str, ...]
    CAPABILITIES: AdapterCapabilities

    def normalize(self, hook: str, payload: JsonObject, mode: HookMode = "observe") -> Event: ...
    def hook_response(
        self,
        hook: str,
        event: Event,
        decision: Decision,
        mode: HookMode,
    ) -> JsonObject: ...
    def unavailable_response(self, hook: str, mode: HookMode = "observe") -> JsonObject: ...
    def hook_configuration(self, data_dir: Path, mode: HookMode = "observe") -> JsonObject: ...


def require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing or invalid {field}")
    return value


def hashed_id(prefix: str, identity: str) -> str:
    return prefix + hashlib.sha256(identity.encode("utf-8")).hexdigest()


def hook_argv(adapter: str, hook: str, data_dir: Path, mode: HookMode) -> list[str]:
    return [
        sys.executable,
        "-m",
        "scrip_core",
        "--data-dir",
        str(data_dir.resolve()),
        "hook",
        adapter,
        "--event",
        hook,
        "--mode",
        mode,
    ]


def hook_handler(adapter: str, hook: str, data_dir: Path, mode: HookMode) -> JsonObject:
    arguments = hook_argv(adapter, hook, data_dir, mode)
    command = subprocess.list2cmdline(arguments) if os.name == "nt" else shlex.join(arguments)
    return {"type": "command", "command": command, "timeout": 5}


@dataclass(frozen=True)
class QuestionFormat:
    label_key: str
    multiple_key: str
    string_options: bool = False


def normalize_questions(raw: object, format: QuestionFormat) -> list[Question]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("Question tool requires questions")
    questions = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("A question must be an object")
        options = item.get("options", [])
        if not isinstance(options, list):
            raise ValueError("Question options must be an array")
        labels = []
        for option in options:
            if format.string_options and isinstance(option, str):
                labels.append(option)
            elif isinstance(option, dict):
                labels.append(require_text(option.get(format.label_key), "question option text"))
            else:
                raise ValueError("Invalid question option")
        questions.append(
            Question(
                text=require_text(item.get("question"), "question text"),
                options=labels,
                multiple=item.get(format.multiple_key, False),
            )
        )
    return questions
