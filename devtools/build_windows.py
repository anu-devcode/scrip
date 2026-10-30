"""Build the Windows bundle and per-user setup; no product installation is performed."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from scrip_core import __version__

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "win32" or not args.compiler.is_file():
        parser.error("A Windows host and installed Inno Setup compiler are required")
    from PIL import Image

    icon = ROOT / "build/native/scrip.ico"
    icon.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(ROOT / "assets/brand/icons/scrip-icon-256.png") as image:
        image.save(icon, sizes=[(16, 16), (32, 32), (48, 48), (128, 128), (256, 256)])
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--distpath",
            "dist",
            "--workpath",
            "build/native",
            "deploy/desktop/scrip.spec",
        ],
        cwd=ROOT,
        check=True,
    )
    bundle = ROOT / "dist/Scrip"
    # An installed app must not need the source checkout, PYTHONPATH, or a system Python.
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    import tempfile

    with tempfile.TemporaryDirectory(prefix="scrip-package-check-") as directory:
        subprocess.run(
            [
                str(bundle / "scrip-cli.exe"),
                "--data-dir",
                str(Path(directory) / "state"),
                "diagnostics",
            ],
            cwd=directory,
            env=environment,
            check=True,
            timeout=40,
        )
    from .native_protocol import check

    check(bundle / "scrip-cli.exe")
    subprocess.run(
        [
            str(args.compiler.resolve()),
            f"/DProductVersion={__version__}",
            str(ROOT / "deploy/desktop/windows.iss"),
        ],
        cwd=ROOT,
        check=True,
    )
    installer = ROOT / f"dist/installers/Scrip-{__version__}-windows-x64-setup.exe"
    if not installer.is_file():
        raise RuntimeError("The compiler did not produce the versioned installer")
    print(f"Built {installer}")


if __name__ == "__main__":
    main()
