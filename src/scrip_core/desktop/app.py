"""Desktop composition and lifecycle; no changes to host applications or hook settings."""

import os
import sys
import tempfile
from contextlib import nullcontext
from pathlib import Path
from threading import Event

from PySide6.QtCore import QThread
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from ..bootstrap import create_service
from ..models import Input, InputRequested, Question, Tool, ToolRequested
from ..service import CompanionService
from .window import InboxWindow
from .worker import DesktopWorker, TraySink


def seed_demo(service: CompanionService, workspace: Path) -> None:
    """Fictional requests only; this function never executes the proposed tool."""
    service.ingest(
        InputRequested(
            event_id="desktop-question",
            operation_id="desktop-question-op",
            adapter="claude-code",
            session_id="demo-conversation",
            workspace=str(workspace),
            kind="input.requested",
            payload=Input(
                source_tool="AskUserQuestion",
                questions=[
                    Question(
                        text="Which database should we use for the prototype?",
                        options=[
                            "SQLite — keep everything local",
                            "PostgreSQL — use a shared server",
                        ],
                    )
                ],
            ),
        )
    )
    service.ingest(
        ToolRequested(
            event_id="desktop-permission",
            operation_id="desktop-permission-op",
            adapter="antigravity",
            session_id="demo-test-run",
            workspace=str(workspace),
            kind="tool.requested",
            payload=Tool(name="run_command", arguments={"CommandLine": "python -m pytest"}),
        )
    )


def run(data_dir: Path, *, demo: bool = False) -> int:
    if sys.platform.startswith("linux") and not any(
        os.environ.get(name) for name in ("DISPLAY", "WAYLAND_DISPLAY", "QT_QPA_PLATFORM")
    ):
        raise ValueError(
            "Desktop requires a graphical session; use the CLI in a headless workspace"
        )
    with (
        tempfile.TemporaryDirectory(prefix="scrip-desktop-demo-")
        if demo
        else nullcontext(str(data_dir)) as directory
    ):
        path = Path(directory).resolve()
        database = path / "scrip.sqlite3"
        if not demo and not database.is_file():
            raise ValueError("Run scrip init with this data directory first, or use desktop --demo")
        service = create_service(database)
        if demo:
            seed_demo(service, path)
        app = QApplication(["scrip"])
        app.setApplicationName("Scrip")
        app.setOrganizationName("Scrip")
        app.setQuitOnLastWindowClosed(False)
        tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        alerts = tray_available and QSystemTrayIcon.supportsMessages()
        window = InboxWindow(tray_available=tray_available, demo=demo)
        tray = QSystemTrayIcon(window.windowIcon(), window)
        tray.setToolTip("Scrip · Agent inbox")
        menu = QMenu()
        show = QAction("Open inbox", menu)
        menu.addAction(show)
        quit_action = QAction("Quit Scrip", menu)
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        stopping = Event()
        sink = TraySink(tray)
        thread = QThread()
        worker = DesktopWorker(service, sink, stopping, alerts=alerts)
        worker.moveToThread(thread)
        thread.started.connect(worker.start)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(app.quit)
        window.request_selected.connect(worker.details)
        window.dismiss_requested.connect(worker.dismiss)
        window.pause_requested.connect(worker.pause)
        window.refresh_requested.connect(worker.refresh)
        worker.snapshot_ready.connect(window.apply_snapshot)
        worker.details_ready.connect(window.show_details)
        worker.notice.connect(window.show_notice)
        worker.problem.connect(window.show_problem)

        def open_inbox() -> None:
            window.showNormal()
            window.raise_()
            window.activateWindow()

        def activated(reason: QSystemTrayIcon.ActivationReason) -> None:
            if reason in (
                QSystemTrayIcon.ActivationReason.Trigger,
                QSystemTrayIcon.ActivationReason.DoubleClick,
            ):
                open_inbox()

        def quit_desktop() -> None:
            window.setEnabled(False)
            window.show_notice("Closing Scrip…")
            stopping.set()
            sink.close()
            thread.quit()

        window.quit_requested.connect(quit_desktop)
        quit_action.triggered.connect(quit_desktop)
        show.triggered.connect(open_inbox)
        tray.activated.connect(activated)
        tray.messageClicked.connect(open_inbox)
        if tray_available:
            tray.show()
        if not alerts:
            window.show_notice("Desktop alerts unavailable in this session · Inbox remains usable.")
        window.show()
        thread.start()
        try:
            return app.exec()
        finally:
            stopping.set()
            sink.close()
            thread.quit()
            thread.wait()
            tray.hide()
