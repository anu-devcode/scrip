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


def test_question_cannot_create_rule_and_stale_details_disable_rule(qapp, companion, input_event):
    result = companion.ingest(input_event)
    window = InboxWindow()
    window.apply_snapshot(snapshot(companion))
    window.show_details(result.request_id, companion.request_details(result.request_id))
    assert not window.rule_button.isEnabled()
    window.show_details(result.request_id, None)
    assert not window.rule_button.isEnabled()
    window.close()


def test_rule_from_real_pending_tool_is_exact_expiring_and_revocable(qapp, companion, tool_event):
    from datetime import timedelta

    result = companion.ingest(tool_event)
    sink = TraySink(FakeTray(available=False))
    worker = DesktopWorker(companion, sink, threading.Event(), alerts=False)
    plans = []
    worker.rule_plan.connect(plans.append)
    worker.plan_rule(result.request_id)
    rule = plans[0]
    assert rule.adapter == tool_event.adapter
    assert rule.workspace == tool_event.workspace
    assert rule.tool == tool_event.payload.name
    assert rule.arguments == tool_event.payload.arguments
    assert rule.action == "allow"
    assert rule.expires_at - companion.clock() == timedelta(hours=24)
    assert companion.rules() == []  # Review is separate from saving.
    worker.save_rule(rule)
    assert companion.rules() == [rule]
    worker.remove_rule(rule.id)
    assert companion.rules() == []
    sink.close()


def test_desktop_first_launch_exits_cleanly_with_no_seeded_data(tmp_path):
    script = """
import sys
from pathlib import Path
from PySide6.QtCore import QTimer
from scrip_core.desktop import app
from scrip_core.bootstrap import create_service
original_application = app.QApplication
class TimedApplication(original_application):
    def exec(self):
        QTimer.singleShot(400, self.quit)
        return super().exec()
app.QApplication = TimedApplication
app.QSystemTrayIcon.isSystemTrayAvailable = lambda: False
root = Path(sys.argv[1])
assert app.run(root) == 0
service = create_service(root / "scrip.sqlite3")
assert service.status().events == 0
assert service.sessions() == []
assert service.inbox() == []
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert result.returncode == 0, result.stderr
    assert "QThread: Destroyed" not in result.stderr
