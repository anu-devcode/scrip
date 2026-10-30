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

from ..connections import ConnectionPlan
from .window import plain_label


class ConnectionsPanel(QWidget):
    review_requested = Signal(str, str)
    apply_requested = Signal(object)
    disconnect_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = plain_label("Connect your workspace")
        title.setObjectName("detailTitle")
        layout.addWidget(title)
        layout.addWidget(
            plain_label(
                "Connect Claude Code using its documented workspace hooks. Choose your project, "
                "review the change, then restart its session. Existing settings are preserved and "
                "backed up. No IDE application files are changed."
            )
        )
        options = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItem("Notifications and visibility", "observe")
        self.mode.addItem("Notifications and exact approval rules", "enforce")
        options.addWidget(self.mode)
        self.connect_button = QPushButton("Connect Claude Code workspace")
        self.connect_button.clicked.connect(self._choose)
        options.addWidget(self.connect_button)
        options.addStretch()
        layout.addLayout(options)
        layout.addWidget(
            plain_label(
                "Notifications mode keeps native permissions unchanged. Rules mode can approve "
                "only actions matching rules you explicitly save. "
                "Other actions need native review. "
                "Questions are answered in Claude Code."
            )
        )
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Workspace", "Mode", "Connection"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 400)
        self.items: list[tuple[str, str, str]] = []
        layout.addWidget(self.table, 1)
        remove = QPushButton("Disconnect selected workspace")
        remove.clicked.connect(self._disconnect)
        layout.addWidget(remove)
        layout.addWidget(
            plain_label(
                "Configured means hooks are installed. Sessions appear only after real agent "
                "events arrive. Claude Code is the guided connection in this release. Other "
                "agents and IDEs need their own supported integration."
            )
        )

    def _choose(self) -> None:
        workspace = QFileDialog.getExistingDirectory(self, "Choose your Claude Code workspace")
        if workspace:
            self.review_requested.emit(workspace, str(self.mode.currentData()))

    @Slot(object)
    def show_plan(self, plan: ConnectionPlan) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Connect Claude Code")
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
    def show_connections(self, items: list[tuple[str, str, str]]) -> None:
        if items == self.items:
            return
        self.items = items
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            for column, value in enumerate(item):
                self.table.setItem(row, column, QTableWidgetItem(value))

    def _disconnect(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item is None:
            return
        workspace = item.text()
        dialog = QDialog(self)
        dialog.setWindowTitle("Disconnect workspace")
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
            self.disconnect_requested.emit(workspace)
