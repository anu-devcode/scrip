"""Guided, explicit workspace connection. Host text is never interpreted as markup."""

from pathlib import Path

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..connections import WORKSPACE_HOSTS, ConnectionPlan, ConnectionStatus, workspace_host
from .window import plain_label


class ConnectionsPanel(QWidget):
    review_requested = Signal(str, str, str)
    apply_requested = Signal(object)
    disconnect_requested = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = plain_label("Connect your workspace")
        title.setObjectName("detailTitle")
        layout.addWidget(title)
        layout.addWidget(
            plain_label(
                "Connect an agent using its documented workspace hooks. Choose your project, "
                "review the change, then restart its session. Existing settings are preserved and "
                "backed up. No IDE application files are changed."
            )
        )
        options = QHBoxLayout()
        self.host = QComboBox()
        self.host.setAccessibleName("Agent to connect")
        for host in WORKSPACE_HOSTS.values():
            self.host.addItem(host.label, host.id)
        options.addWidget(self.host)
        self.mode = QComboBox()
        self.mode.addItem("Notifications and visibility", "observe")
        self.mode.addItem("Notifications and exact approval rules", "enforce")
        options.addWidget(self.mode)
        self.connect_button = QPushButton("Connect workspace")
        self.connect_button.clicked.connect(self._choose)
        options.addWidget(self.connect_button)
        options.addStretch()
        layout.addLayout(options)
        self.guidance = plain_label()
        layout.addWidget(self.guidance)
        self.host.currentIndexChanged.connect(self._host_changed)
        self._host_changed()
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Agent", "Workspace", "Mode", "Connection"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 130)
        self.table.setColumnWidth(1, 360)
        self.items: list[ConnectionStatus] = []
        layout.addWidget(self.table, 1)
        remove = QPushButton("Disconnect selected workspace")
        remove.clicked.connect(self._disconnect)
        layout.addWidget(remove)
        layout.addWidget(
            plain_label(
                "Configured means hooks are installed. Sessions appear only after real agent "
                "events arrive. Claude Code and local, single-root Cursor workspaces have "
                "guided setup. Cloud, remote, multi-root, and other hosts require "
                "separate validation."
            )
        )

    def _host_changed(self) -> None:
        cursor = self.host.currentData() == "cursor"
        self.mode.setItemText(
            0, "Session and completed-tool visibility" if cursor else "Notifications and visibility"
        )
        self.mode.setItemText(
            1,
            "Visibility and shell/MCP rules"
            if cursor
            else "Notifications and exact approval rules",
        )
        self.guidance.setText(
            "Cursor visibility mode adds no permission hooks. Rules mode handles shell and MCP "
            "requests only; other permissions stay in Cursor. Repeated identical calls within "
            "one turn need native review. Native question forwarding is unavailable. "
            "These project hooks reference this computer; do not copy them to cloud agents."
            if cursor
            else "Notifications mode keeps native permissions unchanged. Rules mode approves only "
            "actions matching rules you explicitly save. Other actions need native review. "
            "Questions are answered in Claude Code."
        )

    def _choose(self) -> None:
        host = workspace_host(str(self.host.currentData()))
        workspace = QFileDialog.getExistingDirectory(self, f"Choose your {host.label} workspace")
        if workspace:
            self.review_requested.emit(workspace, str(self.mode.currentData()), host.id)

    @Slot(object)
    def show_plan(self, plan: ConnectionPlan) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Connect {workspace_host(plan.adapter).label}")
        dialog.resize(760, 620)
        layout = QVBoxLayout(dialog)
        layout.addWidget(plain_label(f"Review changes to {plan.target}"))
        layout.addWidget(
            plain_label(
                "Connect saves this workspace configuration and a backup of existing settings. "
                "It does not start an agent or approve any existing request."
            )
        )
        content = QPlainTextEdit()
        content.setReadOnly(True)
        content.setPlainText(plan.content)
        layout.addWidget(content)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Connect workspace")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.apply_requested.emit(plan)

    @Slot(object)
    def show_connections(self, items: list[ConnectionStatus]) -> None:
        if items == self.items:
            return
        selected = self.table.currentRow()
        key = self.items[selected] if 0 <= selected < len(self.items) else None
        self.items = items
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            host = WORKSPACE_HOSTS.get(item.adapter)
            for column, value in enumerate(
                (host.label if host else item.adapter, item.workspace, item.mode, item.status)
            ):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        if key is not None:
            row = next(
                (
                    i
                    for i, item in enumerate(items)
                    if (item.adapter, item.workspace) == (key.adapter, key.workspace)
                ),
                -1,
            )
            if row >= 0:
                self.table.selectRow(row)

    def _disconnect(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        if row >= len(self.items):
            return
        item = self.items[row]
        if item.adapter not in WORKSPACE_HOSTS:
            return
        workspace = item.workspace
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Disconnect {workspace_host(item.adapter).label}")
        layout = QVBoxLayout(dialog)
        layout.addWidget(plain_label(f"Remove Scrip's hooks from {Path(workspace)}?"))
        layout.addWidget(
            plain_label("Other hooks, settings, and your Scrip history stay in place.")
        )
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.disconnect_requested.emit(workspace, item.adapter)
