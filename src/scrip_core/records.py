"""Read and delivery contracts. Database rows never escape the persistence layer."""

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field

from .models import Contract, Event, IngestResult, InputRequested, Rule, ToolRequested


class SessionRecord(Contract):
    adapter: str
    id: str
    workspace: str
    state: Literal["running", "idle", "waiting_input", "waiting_permission", "completed", "failed"]
    model_name: str | None
    updated_at: str


class RequestRecord(Contract):
    id: str
    event_id: str
    operation_id: str | None
    adapter: str
    session_id: str
    workspace: str
    kind: Literal["input", "permission"]
    summary: str
    status: Literal["pending", "acknowledged", "expired", "resolved"]
    created_at: str
    expires_at: str


class NotificationRecord(Contract):
    id: str
    event_id: str
    kind: Literal["input", "permission", "failure"]
    title: str
    state: Literal["queued", "delivering", "delivered", "failed", "dismissed"]
    created_at: str
    delivered_at: str | None
    attempts: int = 0
    last_error: str | None = None


class RequestDetails(Contract):
    request: RequestRecord
    event: Annotated[ToolRequested | InputRequested, Field(discriminator="kind")]


class HistoryEntry(Contract):
    event: Event
    result: IngestResult


class CoreStatus(Contract):
    paused: bool
    events: int
    rules: int


class DeliveryReport(Contract):
    delivered: int = 0
    failed: int = 0
    deferred: int = 0


@dataclass(frozen=True)
class CoreSnapshot:
    status: CoreStatus
    requests: tuple[RequestRecord, ...]
    sessions: tuple[SessionRecord, ...]
    rules: tuple[Rule, ...] = ()
    notifications: tuple[NotificationRecord, ...] = ()
