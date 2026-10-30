"""Native desktop/CLI entry points share the same frozen application bundle."""

import argparse
import sys
from pathlib import Path

from scrip_core.errors import StorageError
from scrip_core.settings import default_data_dir

if Path(sys.executable).stem.lower() == "scrip-cli":
    from scrip_core.cli import main

    raise SystemExit(main())

from scrip_core.desktop.app import run

parser = argparse.ArgumentParser(prog="Scrip")
parser.add_argument("--data-dir", type=Path, default=default_data_dir())
args = parser.parse_args()
try:
    raise SystemExit(run(args.data_dir))
except (ValueError, OSError, StorageError) as error:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication.instance() or QApplication(["Scrip"])
    message = QMessageBox()
    message.setWindowTitle("Scrip")
    message.setTextFormat(Qt.TextFormat.PlainText)
    message.setText(str(error))
    message.exec()
    raise SystemExit(1) from None
