"""Explicit isolated package smoke check. No events, host edits, or native alerts."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..client import Client
from .runtime import LocalRuntime


def check(data_dir: Path) -> None:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication

    from .window import InboxWindow

    if data_dir.exists() and any(data_dir.iterdir()):
        raise ValueError("Diagnostics requires a new, empty directory.")
    runtime = LocalRuntime(data_dir.resolve())
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            service = executor.submit(runtime.start).result()
        assert service.status().events == 0
        assert service.sessions() == [] and service.inbox() == []
        health = Client(runtime.settings).request("/v1/health")
        application = QApplication(["scrip-diagnostics"])
        window = InboxWindow()
        assert not window.windowIcon().isNull(), "Missing application icon"
        window.close()
        application.processEvents()
        print(json.dumps({"ok": True, "version": health["version"], "events": health["events"]}))
    finally:
        runtime.close()
