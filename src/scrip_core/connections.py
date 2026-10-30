"""Explicit, reviewed Claude Code workspace settings. No vendor files or IDE discovery."""

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .adapters import claude_code
from .adapters.common import HookMode
from .settings import private_write


@dataclass(frozen=True)
class ConnectionPlan:
    workspace: Path
    target: Path
    previous: bytes | None
    content: str
    entries: dict[str, Any]
    mode: HookMode


def target_for(workspace: Path) -> Path:
    if not workspace.is_absolute() or not workspace.is_dir() or workspace.is_symlink():
        raise ValueError("Choose an existing workspace folder.")
    folder = workspace / ".claude"
    target = folder / "settings.local.json"
    if folder.is_symlink() or target.is_symlink():
        raise ValueError("Scrip cannot write through a settings symlink.")
    if folder.exists() and not folder.is_dir():
        raise ValueError("The workspace .claude path is not a folder.")
    return target


def read_settings(target: Path) -> tuple[bytes | None, dict[str, Any]]:
    raw = target.read_bytes() if target.exists() else None
    if raw is not None and len(raw) > 1024 * 1024:
        raise ValueError("The settings file is too large to edit safely.")
    doc = json.loads(raw.decode("utf-8-sig")) if raw is not None else {}
    if not isinstance(doc, dict) or not isinstance(doc.get("hooks", {}), dict):
        raise ValueError("The existing Claude Code settings have an unsupported format.")
    return raw, doc


def plan_connection(workspace: Path, data_dir: Path, mode: HookMode) -> ConnectionPlan:
    target = target_for(workspace)
    previous, doc = read_settings(target)
    entries = claude_code.hook_configuration(data_dir, mode)["hooks"]
    hooks = doc.setdefault("hooks", {})
    for name, additions in entries.items():
        existing = hooks.setdefault(name, [])
        if not isinstance(existing, list):
            raise ValueError(f"Existing {name} hooks are not an array.")
        for entry in additions:
            if entry not in existing:
                existing.append(entry)
    return ConnectionPlan(
        workspace, target, previous, json.dumps(doc, indent=2) + "\n", entries, mode
    )


def receipt_path(data_dir: Path, workspace: Path) -> Path:
    key = hashlib.sha256(os.path.normcase(str(workspace)).encode()).hexdigest()
    return data_dir / "connections" / f"{key}.json"


def atomic_settings(target: Path, content: str) -> None:
    descriptor, name = tempfile.mkstemp(prefix="scrip-", suffix=".tmp", dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if target.exists():
            os.chmod(temporary, target.stat().st_mode)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def apply_connection(plan: ConnectionPlan, data_dir: Path) -> None:
    # Revalidate at the write boundary; a user/host edit after preview must not be lost.
    target = target_for(plan.workspace)
    previous, _ = read_settings(target)
    if previous != plan.previous or target != plan.target:
        raise ValueError("Settings changed since review. Open Connect again to refresh.")
    receipt = receipt_path(data_dir, plan.workspace)
    if receipt.exists():
        old = json.loads(receipt.read_text())
        if old["mode"] != plan.mode:
            raise ValueError("Disconnect this workspace before changing its permission mode.")
    target.parent.mkdir(exist_ok=True)
    backup = ""
    if previous is not None:
        backup_path = target.with_name(f"settings.local.json.scrip-backup-{uuid4().hex}")
        private_write(backup_path, previous.decode("utf-8-sig"))
        backup = str(backup_path)
    # Record recovery details before changing host configuration.
    record = json.dumps(
        {
            "workspace": str(plan.workspace),
            "mode": plan.mode,
            "entries": plan.entries,
            "backup": backup,
        },
        indent=2,
    )
    receipt.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_settings(receipt, record)
    atomic_settings(target, plan.content)


def disconnect(workspace: Path, data_dir: Path) -> None:
    target = target_for(workspace)
    receipt = receipt_path(data_dir, workspace)
    record = json.loads(receipt.read_text())
    _, doc = read_settings(target)
    hooks = doc.get("hooks", {})
    for name, entries in record["entries"].items():
        if name in hooks:
            if not isinstance(hooks[name], list):
                raise ValueError("Settings changed; disconnect could not edit this hook safely.")
            hooks[name] = [entry for entry in hooks[name] if entry not in entries]
            if not hooks[name]:
                del hooks[name]
    atomic_settings(target, json.dumps(doc, indent=2) + "\n")
    receipt.unlink()


def connection_status(data_dir: Path) -> list[tuple[str, str, str]]:
    result = []
    for receipt in sorted((data_dir / "connections").glob("*.json")):
        try:
            record = json.loads(receipt.read_text())
            workspace = Path(record["workspace"])
            target = target_for(workspace)
            _, doc = read_settings(target)
            hooks = doc.get("hooks", {})
            valid = all(
                isinstance(hooks.get(name), list) and all(entry in hooks[name] for entry in entries)
                for name, entries in record["entries"].items()
            )
            result.append(
                (str(workspace), record["mode"], "Configured" if valid else "Needs repair")
            )
        except (ValueError, OSError, KeyError, TypeError):
            result.append((str(receipt), "unknown", "Needs repair"))
    return result
