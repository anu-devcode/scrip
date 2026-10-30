"""Capture the actual empty first-launch screen; never populate application state."""

import os
from pathlib import Path


def main() -> None:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    from scrip_core.desktop.window import InboxWindow

    app = QApplication(["scrip-capture"])
    if os.name == "nt":
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf"
        families = QFontDatabase.applicationFontFamilies(
            QFontDatabase.addApplicationFont(str(font))
        )
        if families:
            app.setFont(QFont(families[0]))
    window = InboxWindow()
    window.state.setText("Ready to connect")
    window.count.setText("Connect your first workspace to get started")
    window.show()
    app.processEvents()
    output = Path("dist/desktop.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    if not window.grab().save(str(output)):
        raise RuntimeError("Could not save screenshot")
    window.close()


if __name__ == "__main__":
    main()
