"""Versioned contracts shared by the service and host adapters."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, field_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


def canonical_json(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def workspace_path(value: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("Workspace must be an absolute local path")
    return str(path.resolve())


def finite_arguments(value: dict[str, JsonValue]) -> dict[str, JsonValue]:
    canonical_json(value)
    return value


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


Identifier = Annotated[str, Field(min_length=1, max_length=200, pattern=r"^[^\x00-\x1f]+$")]


class Tool(Contract):
    name: Identifier
    arguments: dict[str, JsonValue] = Field(default_factory=dict)

    _arguments = field_validator("arguments")(finite_arguments)


class Question(Contract):
    text: str = Field(min_length=1, max_length=4000)
    options: list[str] = Field(default_factory=list, max_length=100)
    multiple: bool = False


class Input(Contract):
    questions: list[Question] = Field(min_length=1, max_length=100)
    source_tool: Identifier
    reply_supported: Literal[False] = False


class SessionInfo(Contract):
    model_name: str | None = Field(default=None, max_length=200)
    reason: str | None = Field(default=None, max_length=2000)


class ToolResult(Tool):
    error: str | None = Field(default=None, max_length=4000)


class EventBase(Contract):
    schema_version: Literal[1] = 1
    event_id: Identifier
    adapter: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9_-]+$")
    session_id: Identifier
    workspace: str
    occurred_at: datetime = Field(default_factory=utc_now)

    _workspace = field_validator("workspace")(workspace_path)

    @field_validator("occurred_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Event timestamps must include a timezone")
        return value.astimezone(UTC)

    def fingerprint(self) -> str:
        # Hook retries can have a fresh transport timestamp; semantic content must match.
        data = self.model_dump(mode="json", exclude={"occurred_at"})
        return hashlib.sha256(canonical_json(data).encode()).hexdigest()


class ToolRequested(EventBase):
    kind: Literal["tool.requested"]
    operation_id: Identifier
    policy_mode: Literal["observe", "enforce"] = "enforce"
    payload: Tool


class ToolCompleted(EventBase):
    kind: Literal["tool.completed"]
    operation_id: Identifier
    payload: ToolResult


class InputRequested(EventBase):
    kind: Literal["input.requested"]
    operation_id: Identifier
    payload: Input


class SessionEvent(EventBase):
    kind: Literal[
        "session.started",
        "session.completed",
        "session.failed",
        "session.progress",
        "turn.completed",
        "turn.failed",
    ]
    payload: SessionInfo = Field(default_factory=SessionInfo)


Event = Annotated[
    ToolRequested | ToolCompleted | InputRequested | SessionEvent,
    Field(discriminator="kind"),
]
EVENT = TypeAdapter(Event)


class Decision(Contract):
    action: Literal["allow", "deny", "ask", "none"]
    reason: str
    rule_id: str | None = None


QUESTION_TOOLS = frozenset({"ask_question", "AskUserQuestion", "askQuestion"})


class Rule(Contract):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    adapter: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9_-]+$")
    workspace: str
    tool: Identifier
    arguments: dict[str, JsonValue]
    action: Literal["allow", "deny"]
    session_id: Identifier | None = None
    expires_at: datetime | None = None
    enabled: bool = True

    _workspace = field_validator("workspace")(workspace_path)

    _arguments = field_validator("arguments")(finite_arguments)

    @field_validator("tool")
    @classmethod
    def no_question_rules(cls, value: str) -> str:
        if value in QUESTION_TOOLS:
            raise ValueError("Questions cannot be granted execution approvals")
        return value

    @field_validator("expires_at")
    @classmethod
    def expiry_is_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Rule expiry must include a timezone")
        return value


class IngestResult(Contract):
    event_id: str
    decision: Decision
    request_id: str | None = None
    duplicate: bool = False
