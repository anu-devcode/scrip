"""Delivery status and explicit retry intent; no database or OS alert calls."""

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..records import CoreSnapshot, NotificationRecord
from .window import plain_label

STATES = {
    "queued": "Waiting to send",
    "delivering": "Sending",
    "delivered": "Sent",
    "failed": "Failed",
    "dismissed": "No longer needed",
}


class AlertsPanel(QWidget):
    retry_requested = Signal(str)

    def __init__(self, *, alerts_available: bool) -> None:
        super().__init__()
        self.notifications: tuple[NotificationRecord, ...] = ()
        self.retryable: set[str] = set()
        self.selected_id = ""
        layout = QVBoxLayout(self)
        self.availability = plain_label()
        layout.addWidget(self.availability)
        self.set_available(alerts_available)
        layout.addWidget(
            plain_label(
                "Recent alerts from this computer. Sent does not confirm an alert was displayed "
                "or read. Check system "
                "notification settings if alerts are missing."
            )
        )
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Alert", "Status", "Attempts", "Created (UTC)", "Error"]
        )
        self.table.setAccessibleName("Recent notification delivery status")
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._selected)
        layout.addWidget(self.table, 1)
        self.empty = plain_label("No alerts yet. Alerts appear when a connected agent needs you.")
        layout.addWidget(self.empty)
        layout.addWidget(
            plain_label(
                "Retry is available for failed alerts about pending questions or approvals. "
                "It sends a notification only; answer or approve in the originating agent. "
                "Waiting alerts resume automatically when desktop delivery is available."
            )
        )
        self.retry_button = QPushButton("Retry failed alert")
        self.retry_button.setEnabled(False)
        self.retry_button.clicked.connect(self._retry)
        layout.addWidget(self.retry_button, 0, Qt.AlignmentFlag.AlignRight)

    def set_available(self, available: bool) -> None:
        self.availability.setText(
            "Desktop notification delivery is available."
            if available
            else "Desktop notification delivery is unavailable in this session. Use Inbox."
        )

    def show_snapshot(self, snapshot: CoreSnapshot) -> None:
        pending = {request.event_id for request in snapshot.requests}
        self.retryable = {
            item.id
            for item in snapshot.notifications
            if item.state == "failed" and item.event_id in pending
        }
        if snapshot.notifications != self.notifications:
            self.notifications = snapshot.notifications
            with QSignalBlocker(self.table):
                self.table.setRowCount(len(self.notifications))
                for row, item in enumerate(self.notifications):
                    for column, text in enumerate(
                        (
                            item.title,
                            STATES[item.state],
                            str(item.attempts),
                            item.created_at,
                            item.last_error or "",
                        )
                    ):
                        cell = QTableWidgetItem(text)
                        cell.setData(Qt.ItemDataRole.UserRole, item.id)
                        self.table.setItem(row, column, cell)
                row = next(
                    (i for i, item in enumerate(self.notifications) if item.id == self.selected_id),
                    -1,
                )
                self.table.clearSelection()
                if row >= 0:
                    self.table.selectRow(row)
            self._selected()
        self.empty.setVisible(not self.notifications)
        self.retry_button.setEnabled(self.selected_id in self.retryable)

    def _selected(self) -> None:
        items = self.table.selectedItems()
        self.selected_id = str(items[0].data(Qt.ItemDataRole.UserRole)) if items else ""
        self.retry_button.setEnabled(self.selected_id in self.retryable)

    def _retry(self) -> None:
        if self.selected_id in self.retryable:
            self.retry_button.setEnabled(False)
            self.retry_requested.emit(self.selected_id)
