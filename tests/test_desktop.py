"""Offscreen widgets and GUI handoff tests; native OS alert display is not certified here."""

import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from scrip_core.desktop.presentation import DesktopSnapshot  # noqa: E402
from scrip_core.desktop.window import InboxWindow  # noqa: E402
from scrip_core.desktop.worker import DesktopWorker, TraySink  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    previous = os.environ.get("QT_QPA_PLATFORM")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    application = QApplication.instance() or QApplication(["scrip-tests"])
    yield application
    application.closeAllWindows()
    application.processEvents()
    if previous is None:
        os.environ.pop("QT_QPA_PLATFORM", None)
    else:
        os.environ["QT_QPA_PLATFORM"] = previous


class FakeTray:
    def __init__(self, *, available=True):
        self.available = available
        self.shown = []

    def isSystemTrayAvailable(self):
        return self.available

    def supportsMessages(self):
        return self.available

    def showMessage(self, title, text, icon, timeout):
        self.shown.append((title, text, threading.get_ident()))


def finish_on_gui(qapp, future):
    deadline = time.monotonic() + 5
    while not future.done() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    return future.result(timeout=1)


def snapshot(companion):
    return DesktopSnapshot(
        companion.status(),
        tuple(companion.inbox()),
        tuple(companion.sessions()),
    )


def test_plain_text_and_stale_selection_cannot_target_the_wrong_request(
    qapp, companion, input_event
):
    first = companion.ingest(input_event)
    second = companion.ingest(
        input_event.model_copy(
            update={
                "event_id": "second-request",
                "operation_id": "second-op",
            }
        )
    )
    window = InboxWindow()
    window.apply_snapshot(snapshot(companion))
    window.show_details(first.request_id, companion.request_details(first.request_id))
    assert "Which database?" in window.body.toPlainText()
    window.inbox.setCurrentRow(1)
    window.show_details(first.request_id, companion.request_details(first.request_id))
    assert window.body.toPlainText() == ""
    window.show_details(second.request_id, companion.request_details(second.request_id))
    dismissed = []
    window.dismiss_requested.connect(dismissed.append)
    window.dismiss_button.click()
    assert dismissed == [second.request_id]
    assert len(companion.inbox()) == 2  # The window emits intent; it never executes host actions.
    assert window.guidance.textFormat() == Qt.TextFormat.PlainText
    window.close()


def test_question_markup_is_rendered_as_literal_text(qapp, companion, input_event):
    from scrip_core.models import Input, Question

    text = '<img src="https://example.invalid/private"><script>approve()</script>'
    event = input_event.model_copy(
        update={
            "payload": Input(source_tool="ask_question", questions=[Question(text=text)]),
        }
    )
    result = companion.ingest(event)
    window = InboxWindow()
    window.apply_snapshot(snapshot(companion))
    window.show_details(result.request_id, companion.request_details(result.request_id))
    assert text in window.body.toPlainText()
    assert window.body.isReadOnly()
    assert not hasattr(window, "approve_requested")
    window.close()


def test_tray_handoff_runs_on_gui_thread_and_marks_only_accepted_alert_delivered(
    qapp,
    companion,
    input_event,
):
    companion.ingest(input_event)
    tray = FakeTray()
    sink = TraySink(tray)
    with ThreadPoolExecutor(max_workers=1) as executor:
        report = finish_on_gui(qapp, executor.submit(companion.deliver_notifications, sink))
    assert report.delivered == 1
    assert tray.shown == [("Scrip", "An agent needs your input", threading.get_ident())]
    assert companion.notifications()[0].state == "delivered"
    sink.close()


def test_shutdown_cancels_queued_gui_handoff_and_preserves_notification(
    qapp,
    companion,
    input_event,
):
    companion.ingest(input_event)
    tray = FakeTray()
    sink = TraySink(tray)
    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(companion.deliver_notifications, sink)
        deadline = time.monotonic() + 2
        while not sink.pending and time.monotonic() < deadline:
            time.sleep(0.005)
        assert sink.pending
        sink.close()
        report = result.result(timeout=2)
    qapp.processEvents()
    assert report.deferred == 1
    assert tray.shown == []
    assert companion.notifications()[0].state == "queued"


def test_missing_tray_defers_without_marking_delivery_success(qapp, companion, input_event):
    companion.ingest(input_event)
    sink = TraySink(FakeTray(available=False))
    with ThreadPoolExecutor(max_workers=1) as executor:
        report = finish_on_gui(qapp, executor.submit(companion.deliver_notifications, sink))
    assert report.deferred == 1
    assert companion.notifications()[0].state == "queued"
    sink.close()


def test_timed_out_queued_handoff_cannot_display_late_and_can_retry(qapp, companion, input_event):
    companion.ingest(input_event)
    tray = FakeTray()
    sink = TraySink(tray)
    with ThreadPoolExecutor(max_workers=1) as executor:
        report = executor.submit(companion.deliver_notifications, sink).result(timeout=5)
        assert report.deferred == 1
        qapp.processEvents()  # Process the old queued callback after its ticket was cancelled.
        assert tray.shown == []
        retry = finish_on_gui(qapp, executor.submit(companion.deliver_notifications, sink))
    assert retry.delivered == 1
    assert len(tray.shown) == 1
    assert companion.notifications()[0].attempts == 2
    sink.close()


def test_worker_without_alert_capability_keeps_outbox_queued(qapp, companion, input_event):
    companion.ingest(input_event)
    sink = TraySink(FakeTray(available=False))
    worker = DesktopWorker(companion, sink, threading.Event(), alerts=False)
    snapshots = []
    worker.snapshot_ready.connect(snapshots.append)
    worker.refresh()
    assert len(snapshots[0].requests) == 1
    assert companion.notifications()[0].attempts == 0
    worker.pause(True)
    assert companion.status().paused
    worker.dismiss(companion.inbox()[0].id)
    assert companion.inbox() == []
    sink.close()


def test_refresh_can_retry_details_without_changing_selection(qapp, companion, input_event):
    result = companion.ingest(input_event)
    window = InboxWindow()
    window.apply_snapshot(snapshot(companion))
    selected = []
    window.request_selected.connect(selected.append)
    window._refresh()
    assert selected == [result.request_id]
    window.show_details(result.request_id, companion.request_details(result.request_id))
    window.dismiss_button.click()
    window.show_problem("Temporary failure")
    assert window.dismiss_button.isEnabled()
    assert window.pause_button.isEnabled()
    window.apply_snapshot(snapshot(companion))
    assert "recovered" in window.footer.text()
    window.close()


def test_desktop_demo_exits_cleanly_and_removes_its_temporary_state(tmp_path):
    script = """
import sys
from pathlib import Path
from PySide6.QtCore import QTimer
from scrip_core.desktop import app
original_application = app.QApplication
class TimedApplication(original_application):
    def exec(self):
        QTimer.singleShot(400, self.quit)
        return super().exec()
app.QApplication = TimedApplication
app.QSystemTrayIcon.isSystemTrayAvailable = lambda: False
roots = []
original_seed = app.seed_demo
def seed(service, workspace):
    roots.append(workspace)
    original_seed(service, workspace)
app.seed_demo = seed
assert app.run(Path(sys.argv[1]), demo=True) == 0
assert roots and not roots[0].exists()
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "QThread: Destroyed" not in result.stderr
    assert list(tmp_path.iterdir()) == []
