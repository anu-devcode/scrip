"""Database work runs on one Qt worker thread; widgets stay on the GUI thread."""

from concurrent.futures import CancelledError, Future, TimeoutError
from dataclasses import dataclass
from threading import Event, Lock

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import QSystemTrayIcon

from ..errors import DeliveryDeferred
from ..records import NotificationRecord
from ..service import CompanionService
from .presentation import DesktopSnapshot


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
    ) -> None:
        super().__init__()
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
            requests = tuple(self.service.inbox())
            status = self.service.status()
            sessions = tuple(self.service.sessions())
            if self.stopping.is_set():
                return
            self.snapshot_ready.emit(DesktopSnapshot(status, requests, sessions))
            if self.alerts:
                # One per tick limits alert bursts and keeps delivery within its lease.
                self.service.deliver_notifications(self.sink, limit=1)
        except Exception as error:
            self.problem.emit(f"Refresh failed ({type(error).__name__}). Retrying shortly.")

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
