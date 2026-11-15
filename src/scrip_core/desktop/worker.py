"""Database work runs on one Qt worker thread; widgets stay on the GUI thread."""

from concurrent.futures import CancelledError, Future, TimeoutError
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from threading import Event, Lock
from uuid import uuid4

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import QSystemTrayIcon

from ..connections import (
    ConnectionPlan,
    apply_connection,
    connection_status,
    disconnect,
    plan_connection,
    workspace_host,
)
from ..errors import DeliveryDeferred
from ..models import Rule, ToolRequested
from ..records import NotificationRecord
from ..service import CompanionService


@dataclass(frozen=True)
class AlertTicket:
    notification: NotificationRecord
    accepted: Future[None]


class TraySink(QObject):
    """A bounded GUI handoff. Cancelled queued tickets cannot display later."""

    requested = Signal(object)

    def __init__(self, tray: QSystemTrayIcon) -> None:
        super().__init__()
        self.tray = tray
        self.closed = Event()
        self.lock = Lock()
        self.pending: set[Future[None]] = set()
        self.requested.connect(self._display, Qt.ConnectionType.QueuedConnection)

    def send(self, notification: NotificationRecord) -> None:
        accepted: Future[None] = Future()
        with self.lock:
            if self.closed.is_set():
                raise DeliveryDeferred()
            self.pending.add(accepted)
        try:
            self.requested.emit(AlertTicket(notification, accepted))
            accepted.result(timeout=3)
        except (CancelledError, TimeoutError):
            accepted.cancel()
            raise DeliveryDeferred() from None
        finally:
            with self.lock:
                self.pending.discard(accepted)

    @Slot(object)
    def _display(self, ticket: AlertTicket) -> None:
        if not ticket.accepted.set_running_or_notify_cancel():
            return
        try:
            if (
                self.closed.is_set()
                or not self.tray.isSystemTrayAvailable()
                or not self.tray.supportsMessages()
            ):
                raise DeliveryDeferred()
            self.tray.showMessage(
                "Scrip",
                ticket.notification.title,
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )
        except Exception as error:
            ticket.accepted.set_exception(error)
        else:
            ticket.accepted.set_result(None)

    def close(self) -> None:
        with self.lock:
            self.closed.set()
            for future in self.pending:
                future.cancel()


class DesktopWorker(QObject):
    rule_plan = Signal(object)
    connection_plan = Signal(object)
    connections_ready = Signal(object)
    snapshot_ready = Signal(object)
    details_ready = Signal(str, object)
    notice = Signal(str)
    problem = Signal(str)

    def __init__(
        self,
        service: CompanionService,
        sink: TraySink,
        stopping: Event,
        *,
        alerts: bool,
        data_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self.data_dir = data_dir
        self.service = service
        self.sink = sink
        self.stopping = stopping
        self.alerts = alerts
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.refresh)

    @Slot()
    def start(self) -> None:
        self.refresh()
        self.timer.start()

    @Slot()
    def refresh(self) -> None:
        if self.stopping.is_set():
            return
        try:
            snapshot = self.service.snapshot()
            if self.stopping.is_set():
                return
            self.snapshot_ready.emit(snapshot)
            if self.data_dir is not None:
                self.connections_ready.emit(connection_status(self.data_dir))
            if self.alerts:
                # One per tick limits alert bursts and keeps delivery within its lease.
                self.service.deliver_notifications(self.sink, limit=1)
        except Exception as error:
            self.problem.emit(f"Refresh failed ({type(error).__name__}). Retrying shortly.")

    @Slot(str)
    def retry_notification(self, notification_id: str) -> None:
        if self.stopping.is_set():
            return
        try:
            retried = self.service.retry_notification(notification_id)
            self.refresh()
            self.notice.emit(
                "Alert queued again. Delivery waits for desktop alerts to be available."
                if retried
                else "This alert cannot be retried. Its request may no longer be pending."
            )
        except Exception as error:
            self.problem.emit(f"Could not retry alert ({type(error).__name__}).")

    @Slot(str)
    def details(self, request_id: str) -> None:
        if self.stopping.is_set():
            return
        try:
            self.details_ready.emit(request_id, self.service.request_details(request_id))
        except Exception as error:
            self.problem.emit(f"Could not load request ({type(error).__name__}).")

    @Slot(str)
    def dismiss(self, request_id: str) -> None:
        if self.stopping.is_set():
            return
        try:
            dismissed = self.service.acknowledge(request_id)
            self.refresh()
            self.notice.emit(
                "Dismissed locally. The originating agent has not received an answer."
                if dismissed
                else "This request is no longer pending."
            )
        except Exception as error:
            self.problem.emit(f"Could not dismiss request ({type(error).__name__}).")

    @Slot(bool)
    def pause(self, paused: bool) -> None:
        if self.stopping.is_set():
            return
        try:
            self.service.set_paused(paused)
            self.refresh()
        except Exception as error:
            self.problem.emit(f"Could not change pause state ({type(error).__name__}).")

    @Slot(str, str, str)
    def plan_connection(self, workspace: str, mode: str, adapter: str) -> None:
        if self.stopping.is_set() or self.data_dir is None:
            return
        try:
            if mode not in ("observe", "enforce"):
                raise ValueError("Unknown connection mode")
            self.connection_plan.emit(
                plan_connection(
                    Path(workspace),
                    self.data_dir,
                    "enforce" if mode == "enforce" else "observe",
                    adapter,
                )
            )
        except (ValueError, OSError) as error:
            self.problem.emit(str(error))

    @Slot(object)
    def connect_workspace(self, plan: ConnectionPlan) -> None:
        if self.stopping.is_set() or self.data_dir is None:
            return
        try:
            apply_connection(plan, self.data_dir)
            self.refresh()
            self.notice.emit(
                f"Workspace configured. Start a new {workspace_host(plan.adapter).label} "
                "session in this project."
            )
        except (ValueError, OSError) as error:
            self.problem.emit(str(error))

    @Slot(str, str)
    def disconnect_workspace(self, workspace: str, adapter: str) -> None:
        if self.stopping.is_set() or self.data_dir is None:
            return
        try:
            disconnect(Path(workspace), self.data_dir, adapter)
            self.refresh()
            self.notice.emit(
                f"Disconnected. Restart {workspace_host(adapter).label} to reload its hooks."
            )
        except (ValueError, OSError) as error:
            self.problem.emit(str(error))

    @Slot(str)
    def plan_rule(self, request_id: str) -> None:
        if self.stopping.is_set():
            return
        try:
            details = self.service.request_details(request_id)
            if details is None or not isinstance(details.event, ToolRequested):
                raise ValueError("Select a pending approval request to create a rule.")
            event = details.event
            self.rule_plan.emit(
                Rule(
                    id="desktop-" + uuid4().hex,
                    adapter=event.adapter,
                    workspace=event.workspace,
                    tool=event.payload.name,
                    arguments=event.payload.arguments,
                    action="allow",
                    expires_at=self.service.clock() + timedelta(hours=24),
                )
            )
        except (ValueError, OSError) as error:
            self.problem.emit(str(error))

    @Slot(object)
    def save_rule(self, rule: Rule) -> None:
        if self.stopping.is_set():
            return
        try:
            self.service.put_rule(rule)
            self.refresh()
            self.notice.emit(
                "Rule saved for future matching calls. Review the current prompt in your agent."
            )
        except (ValueError, OSError) as error:
            self.problem.emit(str(error))

    @Slot(str)
    def remove_rule(self, rule_id: str) -> None:
        if self.stopping.is_set():
            return
        try:
            self.service.remove_rule(rule_id)
            self.refresh()
            self.notice.emit("Rule removed.")
        except (ValueError, OSError) as error:
            self.problem.emit(str(error))
