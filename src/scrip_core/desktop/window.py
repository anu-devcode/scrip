"""Native widgets for the local inbox. Untrusted event text is always plain text."""

from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..records import CoreSnapshot, RequestDetails, RequestRecord
from .presentation import request_text

STYLE = """
QMainWindow, QWidget { background: #101619; color: #e7eeee; font-size: 13px; }
QLabel#brand { color: #80dfbf; font-size: 15px; font-weight: 700; letter-spacing: 3px; }
QLabel#heading { font-size: 26px; font-weight: 600; }
QLabel#subtle, QLabel#count, QLabel#footer { color: #a2b3b8; }
QLabel#state { color: #80dfbf; background: #1a302b; padding: 7px 12px; border-radius: 12px; }
QLabel#detailTitle { font-size: 21px; font-weight: 600; }
QFrame#details QLabel#guidance {
    color: #b7cbc5; background: #1a2929; padding: 14px; border-radius: 8px;
}
QPushButton {
    background: #233136; border: 1px solid #35494f; border-radius: 7px; padding: 9px 14px;
}
QPushButton:hover { background: #30464b; border-color: #80dfbf; }
QPushButton:focus { border: 2px solid #80dfbf; }
QPushButton:disabled { color: #62767c; border-color: #263439; }
QPushButton#dismiss { color: #b3ecd8; border-color: #4b8c78; }
QTabWidget::pane { border: 0; }
QTabBar::tab { padding: 12px 18px; color: #9fb1b7; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #80dfbf; border-bottom: 2px solid #80dfbf; }
QListWidget { border: 1px solid #293a40; background: #151e22; border-radius: 9px; padding: 5px; }
QListWidget::item {
    padding: 16px 12px; margin: 3px; border-radius: 6px; border-bottom: 1px solid #27383d;
}
QListWidget::item:selected { background: #233e39; color: #e2fff5; }
QListWidget::item:hover:!selected { background: #203035; }
QFrame#details { background: #151e22; border: 1px solid #293a40; border-radius: 9px; }
QFrame#details QLabel { background: transparent; }
QPlainTextEdit {
    background: #10181c; border: 1px solid #293a40; border-radius: 7px; padding: 12px;
}
QTableWidget { background: #151e22; border: 1px solid #293a40; gridline-color: #26383e; }
QTableWidget::item { padding: 10px; }
QHeaderView::section { background: #203035; color: #b7cbc5; padding: 12px; border: 0; }
QSplitter::handle { background: #101619; width: 16px; }
"""


def scrip_icon() -> QIcon:
    return QIcon(str(Path(__file__).with_name("assets") / "scrip-icon.png"))


def plain_label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class InboxWindow(QMainWindow):
    request_selected = Signal(str)
    dismiss_requested = Signal(str)
    rule_requested = Signal(str)
    pause_requested = Signal(bool)
    refresh_requested = Signal()
    quit_requested = Signal()

    def __init__(self, *, tray_available: bool = False) -> None:
        super().__init__()
        self.tray_available = tray_available
        self.requests: tuple[RequestRecord, ...] = ()
        self.selected_id = ""
        self.paused = False
        self.problem_active = False
        self.setWindowTitle("Scrip · Agent inbox")
        self.setWindowIcon(scrip_icon())
        self.resize(1120, 760)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(STYLE)
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(18)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        brand = plain_label("SCRIP")
        brand.setObjectName("brand")
        titles.addWidget(brand)
        heading = plain_label("Your agents, in view")
        heading.setObjectName("heading")
        titles.addWidget(heading)
        header.addLayout(titles)
        header.addStretch()
        self.state = plain_label("Loading local state")
        self.state.setObjectName("state")
        header.addWidget(self.state)
        layout.addLayout(header)
        actions = QHBoxLayout()
        self.count = plain_label("Waiting for the first refresh…")
        self.count.setObjectName("count")
        actions.addWidget(self.count, 1)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh)
        actions.addWidget(refresh)
        self.pause_button = QPushButton("Pause auto approvals")
        self.pause_button.clicked.connect(self._pause)
        actions.addWidget(self.pause_button)
        quit_button = QPushButton("Quit")
        quit_button.clicked.connect(self.quit_requested.emit)
        actions.addWidget(quit_button)
        layout.addLayout(actions)
        self.tabs = QTabWidget()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.inbox = QListWidget()
        self.inbox.setWordWrap(True)
        self.inbox.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.inbox.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.inbox.setAccessibleName("Pending agent requests")
        self.inbox.currentItemChanged.connect(self._selected)
        splitter.addWidget(self.inbox)
        details = QFrame()
        details.setObjectName("details")
        detail_layout = QVBoxLayout(details)
        detail_layout.setContentsMargins(22, 22, 22, 22)
        detail_layout.setSpacing(16)
        self.detail_title = plain_label("Nothing needs your attention")
        self.detail_title.setObjectName("detailTitle")
        detail_layout.addWidget(self.detail_title)
        self.guidance = plain_label(
            "Questions and approval requests will appear here when a connected agent needs you."
        )
        self.guidance.setObjectName("guidance")
        detail_layout.addWidget(self.guidance)
        form = QFormLayout()
        self.host = plain_label("—")
        self.workspace = plain_label("—")
        self.session = plain_label("—")
        for title, value in (
            ("Agent", self.host),
            ("Workspace", self.workspace),
            ("Session", self.session),
        ):
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(title, value)
        detail_layout.addLayout(form)
        self.body = QPlainTextEdit()
        self.body.setReadOnly(True)
        self.body.setAccessibleName("Full request details")
        detail_layout.addWidget(self.body, 1)
        self.dismiss_button = QPushButton("Dismiss locally")
        self.dismiss_button.setObjectName("dismiss")
        self.dismiss_button.setEnabled(False)
        self.dismiss_button.clicked.connect(self._dismiss)
        self.rule_button = QPushButton("Create exact approval rule...")
        self.rule_button.setEnabled(False)
        self.rule_button.clicked.connect(lambda: self.rule_requested.emit(self.selected_id))
        detail_layout.addWidget(self.rule_button)
        detail_layout.addWidget(self.dismiss_button, 0, Qt.AlignmentFlag.AlignRight)
        splitter.addWidget(details)
        splitter.setSizes([340, 700])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        self.tabs.addTab(splitter, "Inbox")
        self.sessions = QTableWidget(0, 4)
        self.sessions.setHorizontalHeaderLabels(["Agent", "Session", "State", "Workspace"])
        self.sessions.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.sessions.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.sessions.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.sessions.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.sessions, "Sessions")
        from .connections import ConnectionsPanel

        self.connections = ConnectionsPanel()
        self.tabs.addTab(self.connections, "Connections")
        from .rules import RulesPanel

        self.rules_panel = RulesPanel()
        self.tabs.addTab(self.rules_panel, "Rules")
        from .alerts import AlertsPanel

        self.alerts_panel = AlertsPanel(alerts_available=tray_available)
        self.tabs.addTab(self.alerts_panel, "Alerts")
        self.tabs.setCurrentWidget(self.connections)
        layout.addWidget(self.tabs, 1)
        self.footer = plain_label(
            "Desktop alerts active · Closing the window keeps Scrip in the tray."
            if tray_available
            else "Desktop alerts unavailable in this session · Inbox remains usable."
        )
        self.footer.setObjectName("footer")
        layout.addWidget(self.footer)
        self.setCentralWidget(root)

    @Slot(object)
    def apply_snapshot(self, snapshot: CoreSnapshot) -> None:
        self.alerts_panel.show_snapshot(snapshot)
        if self.problem_active:
            self.footer.setText("Local state refreshed. Connection recovered.")
            self.problem_active = False
        self.rules_panel.show_rules(snapshot.rules)
        self.paused = snapshot.status.paused
        self.state.setText("Auto approvals paused" if self.paused else "Local connection active")
        self.pause_button.setText(
            "Resume auto approvals" if self.paused else "Pause auto approvals"
        )
        self.pause_button.setEnabled(True)
        questions = sum(item.kind == "input" for item in snapshot.requests)
        approvals = len(snapshot.requests) - questions
        question_label = "question" if questions == 1 else "questions"
        approval_label = "approval request" if approvals == 1 else "approval requests"
        self.count.setText(
            f"{len(snapshot.requests)} waiting · {questions} {question_label} · "
            f"{approvals} {approval_label}"
        )
        if snapshot.requests != self.requests:
            self.requests = snapshot.requests
            with QSignalBlocker(self.inbox):
                self.inbox.clear()
                for request in self.requests:
                    kind = "Question" if request.kind == "input" else "Approval request"
                    summary = " ".join(request.summary.split())[:115]
                    item = QListWidgetItem(
                        f"{kind} · {request.adapter}\n{summary}\n{Path(request.workspace).name}"
                    )
                    item.setData(Qt.ItemDataRole.UserRole, request.id)
                    self.inbox.addItem(item)
                row = next(
                    (i for i, item in enumerate(self.requests) if item.id == self.selected_id), 0
                )
                self.inbox.setCurrentRow(row)
            self._selected(self.inbox.currentItem(), None)
        self.sessions.setRowCount(len(snapshot.sessions))
        for row, session in enumerate(snapshot.sessions):
            for column, text in enumerate(
                (session.adapter, session.id, session.state.replace("_", " "), session.workspace)
            ):
                self.sessions.setItem(row, column, QTableWidgetItem(text))

    def _selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        self.selected_id = str(current.data(Qt.ItemDataRole.UserRole)) if current else ""
        self.body.clear()
        self.rule_button.setEnabled(False)
        self.dismiss_button.setEnabled(False)
        for label in (self.host, self.workspace, self.session):
            label.setText("—")
        if self.selected_id:
            self.detail_title.setText("Loading request…")
            self.guidance.setText("Loading this request from local state…")
            self.request_selected.emit(self.selected_id)
        else:
            self.detail_title.setText("Nothing needs your attention")
            self.guidance.setText("New requests will appear here. Keep working in your agents.")

    @Slot(str, object)
    def show_details(self, request_id: str, details: RequestDetails | None) -> None:
        if request_id != self.selected_id:
            return  # A slower result must not replace a newer selection.
        if details is None:
            self.body.clear()
            self.detail_title.setText("This request is no longer pending")
            self.dismiss_button.setEnabled(False)
            self.rule_button.setEnabled(False)
            return
        question = details.request.kind == "input"
        self.rule_button.setEnabled(not question)
        self.detail_title.setText("Your input is needed" if question else "Review in the agent")
        self.guidance.setText(
            "Answer in the originating agent. Dismissing here only clears this local inbox item."
            if question
            else (
                "Approve or deny in the originating agent. "
                "Dismissing here does not grant permission."
            )
        )
        self.host.setText(details.request.adapter)
        self.workspace.setText(details.request.workspace)
        self.session.setText(details.request.session_id)
        self.body.setPlainText(request_text(details))
        self.dismiss_button.setEnabled(True)

    @Slot()
    def _refresh(self) -> None:
        self.refresh_requested.emit()
        if self.selected_id:
            self.request_selected.emit(self.selected_id)

    @Slot()
    def _dismiss(self) -> None:
        if self.selected_id:
            self.dismiss_button.setEnabled(False)
            self.dismiss_requested.emit(self.selected_id)

    @Slot()
    def _pause(self) -> None:
        self.pause_button.setEnabled(False)
        self.pause_requested.emit(not self.paused)

    @Slot(str)
    def show_notice(self, text: str) -> None:
        self.footer.setText(text)
        self.problem_active = False

    @Slot(str)
    def show_problem(self, text: str) -> None:
        self.footer.setText(text)
        self.problem_active = True
        self.pause_button.setEnabled(True)
        self.dismiss_button.setEnabled(bool(self.selected_id and self.body.toPlainText()))

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.tray_available:
            self.hide()
            event.ignore()
        else:
            event.accept()
            self.quit_requested.emit()
