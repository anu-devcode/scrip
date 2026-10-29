from __future__ import annotations

import json
import os
import secrets
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path


def default_data_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "Scrip"
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "scrip"


def private_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(content)


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    port: int = 8765

    @property
    def database(self) -> Path:
        return self.data_dir / "scrip.sqlite3"

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def initialize(self) -> None:
        if not 1 <= self.port <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        token_file = self.data_dir / "api-token"
        if not token_file.exists():
            with suppress(FileExistsError):
                private_write(token_file, secrets.token_urlsafe(32))
        config = self.data_dir / "connection.json"
        if not config.exists():
            with suppress(FileExistsError):
                private_write(config, json.dumps({"base_url": self.base_url}, indent=2))

    def token(self) -> str:
        token = (self.data_dir / "api-token").read_text(encoding="utf-8").strip()
        if len(token) < 32:
            raise ValueError("Invalid Scrip API token")
        return token
