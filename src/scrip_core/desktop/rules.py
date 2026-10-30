"""Review and revoke exact, time-limited approval rules in the desktop."""

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import Rule
from .window import plain_label


class RulesPanel(QWidget):
    save_requested = Signal(object)
    remove_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(
            plain_label(
                "Rules allow only the exact agent, workspace, tool, and complete arguments you "
                "review. Create a rule from an approval request in the Inbox. New desktop rules "
                "expire after 24 hours. Pause all rules at any time using the button above."
            )
        )
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Rule", "Tool", "Workspace", "Expires"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.rules: tuple[Rule, ...] = ()
        layout.addWidget(self.table)
        remove = QPushButton("Remove selected rule")
        remove.clicked.connect(self._remove)
        layout.addWidget(remove)

    @Slot(object)
    def show_rules(self, rules: tuple[Rule, ...]) -> None:
        if rules == self.rules:
            return
        self.rules = rules
        self.table.setRowCount(len(rules))
        for row, rule in enumerate(rules):
            values = (
                rule.id,
                rule.tool,
                rule.workspace,
                rule.expires_at.isoformat() if rule.expires_at else "No expiry",
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))

    def _remove(self) -> None:
        row = self.table.currentRow()
        if row >= 0 and (item := self.table.item(row, 0)) is not None:
            self.remove_requested.emit(item.text())

    @Slot(object)
    def review_rule(self, rule: Rule) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Allow this exact action for 24 hours")
        dialog.resize(720, 560)
        layout = QVBoxLayout(dialog)
        layout.addWidget(
            plain_label(
                "Future matching calls in this workspace can run automatically in Rules mode. "
                "This does not approve the currently displayed native prompt. Review that "
                "prompt in your agent. Questions can never be approved by a rule."
            )
        )
        content = QPlainTextEdit()
        content.setReadOnly(True)
        content.setPlainText(rule.model_dump_json(indent=2))
        layout.addWidget(content)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.save_requested.emit(rule)
