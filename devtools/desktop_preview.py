"""Render an offscreen desktop preview with temporary fictional requests."""

import os
import sys
import tempfile
from pathlib import Path

from scrip_core.bootstrap import create_service


def main() -> None:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    from scrip_core.desktop.app import seed_demo
    from scrip_core.desktop.presentation import DesktopSnapshot
    from scrip_core.desktop.window import InboxWindow

    app = QApplication(["scrip-preview"])
    if sys.platform == "win32":
        # The offscreen Windows plugin has no native font database. Load, never bundle, a font.
        font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf"
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0]))
    with tempfile.TemporaryDirectory(prefix="scrip-desktop-preview-") as directory:
        root = Path(directory).resolve()
        service = create_service(root / "scrip.sqlite3")
        public_workspace = (
            Path("C:/Projects/scrip-demo")
            if sys.platform == "win32"
            else Path("/workspaces/scrip-demo")
        )
        seed_demo(service, public_workspace)
        window = InboxWindow(demo=True)
        window.apply_snapshot(
            DesktopSnapshot(
                service.status(),
                tuple(service.inbox()),
                tuple(service.sessions()),
            )
        )
        selected = service.inbox()[0]
        window.show_details(selected.id, service.request_details(selected.id))
        window.show()
        app.processEvents()
        output = Path("dist/desktop-preview.png").resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        if not window.grab().save(str(output)):
            raise RuntimeError("Could not save desktop preview")
        window.close()
    print(f"Desktop preview: {output}")


if __name__ == "__main__":
    main()
