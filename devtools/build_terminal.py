"""Build and verify the console-only bundle and per-user installer."""

import argparse
import subprocess
import sys
from pathlib import Path

from scrip_core import __version__

from .native_project import check


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", required=True, type=Path)
    args = parser.parse_args()
    if sys.platform != "win32" or not args.compiler.is_file():
        parser.error("Windows and the Inno Setup compiler are required")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--distpath",
            "dist",
            "--workpath",
            "build/terminal",
            "deploy/terminal/scrip-terminal.spec",
        ],
        check=True,
    )
    check(Path("dist/ScripTerminal/scrip.exe"))
    subprocess.run(
        [
            str(args.compiler.resolve()),
            f"/DProductVersion={__version__}",
            str(Path("deploy/terminal/windows.iss").resolve()),
        ],
        check=True,
    )
    print(f"Built dist/installers/Scrip-Terminal-{__version__}-windows-x64-setup.exe")


if __name__ == "__main__":
    main()
