import subprocess
import sys

import pytest

from scrip_core import commands
from scrip_core.cli import parser


def test_headless_cli_does_not_import_qt():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; from scrip_core.cli import parser; "
                "assert not any(name.startswith('PySide6') for name in sys.modules); "
                "assert parser().parse_args(['status']).command == 'status'"
            ),
        ],
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_missing_desktop_extra_gives_installation_instruction_without_creating_state(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(commands, "find_spec", lambda _: None)
    args = parser().parse_args(["--data-dir", str(tmp_path / "unused"), "desktop", "--demo"])
    with pytest.raises(ValueError, match="uv sync --locked --extra desktop"):
        commands.desktop(args)
    assert not (tmp_path / "unused").exists()
