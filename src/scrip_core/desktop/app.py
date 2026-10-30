"""Desktop composition and lifecycle; no changes to host applications or hook settings."""

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

from PySide6.QtCore import QLockFile, QThread
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .runtime import LocalRuntime
from .window import InboxWindow
from .worker import DesktopWorker, TraySink


def run(data_dir: Path) -> int:
    if sys.platform.startswith("linux") and not any(
        os.environ.get(name) for name in ("DISPLAY", "WAYLAND_DISPLAY", "QT_QPA_PLATFORM")
    ):
        raise ValueError(
            "Desktop requires a graphical session; use the CLI in a headless workspace"
        )
    path = data_dir.resolve()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = QLockFile(str(path / "desktop.lock"))
    if not lock.tryLock(0):
        raise ValueError("Scrip is already running. Open it from the system tray.")
    runtime = LocalRuntime(path)
    try:
        with ThreadPoolExecutor(max_workers=1) as startup:
            service = startup.submit(runtime.start).result()
        app = QApplication(["scrip"])
        app.setApplicationName("Scrip")
        app.setOrganizationName("Scrip")
        app.setQuitOnLastWindowClosed(False)
        tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        alerts = tray_available and QSystemTrayIcon.supportsMessages()
        window = InboxWindow(tray_available=tray_available)
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
        worker = DesktopWorker(service, sink, stopping, alerts=alerts, data_dir=path)
        worker.moveToThread(thread)
        thread.started.connect(worker.start)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(app.quit)
        window.connections.review_requested.connect(worker.plan_connection)
        window.connections.apply_requested.connect(worker.connect_workspace)
        window.connections.disconnect_requested.connect(worker.disconnect_workspace)
        worker.connection_plan.connect(window.connections.show_plan)
        worker.connections_ready.connect(window.connections.show_connections)
        window.rule_requested.connect(worker.plan_rule)
        worker.rule_plan.connect(window.rules_panel.review_rule)
        window.rules_panel.save_requested.connect(worker.save_rule)
        window.rules_panel.remove_requested.connect(worker.remove_rule)
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
    finally:
        runtime.close()
        lock.unlock()
