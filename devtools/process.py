"""Owned local service processes shared by integration tests and the isolated demo."""

import json
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scrip_core.adapters.common import HookMode, hook_argv
from scrip_core.bootstrap import create_service
from scrip_core.client import Client
from scrip_core.service import CompanionService
from scrip_core.settings import Settings


@dataclass(frozen=True)
class LocalService:
    settings: Settings
    client: Client
    companion: CompanionService
    workspace: Path


@contextmanager
def running_service(workspace: Path) -> Iterator[LocalService]:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    settings = Settings(workspace / "state with spaces", port=port)
    settings.initialize()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "scrip_core",
            "--data-dir",
            str(settings.data_dir),
            "serve",
            "--port",
            str(port),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    client = Client(settings, timeout=0.5)
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if process.poll() is not None:
                assert process.stderr is not None
                raise RuntimeError(process.stderr.read())
            try:
                client.request("/v1/health")
                break
            except (OSError, ValueError):
                time.sleep(0.05)
        else:
            raise RuntimeError("Local service did not start")
        yield LocalService(settings, client, create_service(settings.database), workspace)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        assert process.stderr is not None
        process.stderr.close()


def invoke_hook(
    settings: Settings,
    adapter: str,
    payload: dict[str, Any],
    hook: str = "PreToolUse",
    mode: HookMode = "enforce",
    *,
    command: str | None = None,
) -> dict[str, Any]:
    """Execute Scrip's hook entry point only, never a proposed tool command."""
    result = subprocess.run(
        command if command is not None else hook_argv(adapter, hook, settings.data_dir, mode),
        shell=command is not None,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=15,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode or result.stderr:
        raise RuntimeError(result.stderr or f"Hook exited with {result.returncode}")
    parsed = json.loads(result.stdout)
    if not isinstance(parsed, dict):
        raise ValueError("Hook response must be an object")
    return parsed
