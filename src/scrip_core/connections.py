"""Explicit, reviewed workspace hooks with shared ownership and atomic file mechanics."""

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .adapters.common import HookMode
from .adapters.registry import get_adapter
from .settings import private_write


@dataclass(frozen=True)
class WorkspaceHost:
    id: str
    label: str
    folder: str
    filename: str
    version: int | None = None


WORKSPACE_HOSTS = {
    "claude-code": WorkspaceHost("claude-code", "Claude Code", ".claude", "settings.local.json"),
    "cursor": WorkspaceHost("cursor", "Cursor", ".cursor", "hooks.json", version=1),
}


def workspace_host(adapter: str) -> WorkspaceHost:
    try:
        return WORKSPACE_HOSTS[adapter]
    except KeyError:
        raise ValueError("This agent does not have guided workspace setup.") from None


@dataclass(frozen=True)
class ConnectionPlan:
    workspace: Path
    target: Path
    previous: bytes | None
    content: str
    entries: dict[str, Any]
    mode: HookMode
    adapter: str = "claude-code"


@dataclass(frozen=True)
class ConnectionStatus:
    workspace: str
    adapter: str
    mode: str
    status: str


def target_for(workspace: Path, adapter: str = "claude-code") -> Path:
    host = workspace_host(adapter)
    if not workspace.is_absolute() or not workspace.is_dir() or workspace.is_symlink():
        raise ValueError("Choose an existing workspace folder.")
    folder = workspace / host.folder
    target = folder / host.filename
    if folder.is_symlink() or target.is_symlink():
        raise ValueError("Scrip cannot write through a settings symlink.")
    if folder.exists() and not folder.is_dir():
        raise ValueError(f"The workspace {host.folder} path is not a folder.")
    return target


def read_settings(
    target: Path, adapter: str = "claude-code"
) -> tuple[bytes | None, dict[str, Any]]:
    host = workspace_host(adapter)
    raw = target.read_bytes() if target.exists() else None
    if raw is not None and len(raw) > 1024 * 1024:
        raise ValueError("The settings file is too large to edit safely.")
    doc = json.loads(raw.decode("utf-8-sig")) if raw is not None else {}
    if not isinstance(doc, dict) or not isinstance(doc.get("hooks", {}), dict):
        raise ValueError(f"The existing {host.label} settings have an unsupported format.")
    if (
        host.version is not None
        and "version" in doc
        and (type(doc["version"]) is not int or doc["version"] != host.version)
    ):
        raise ValueError(f"Unsupported {host.label} hook configuration version.")
    return raw, doc


def plan_connection(
    workspace: Path, data_dir: Path, mode: HookMode, adapter: str = "claude-code"
) -> ConnectionPlan:
    if mode not in ("observe", "enforce"):
        raise ValueError("Unknown connection mode")
    host = workspace_host(adapter)
    target = target_for(workspace, adapter)
    previous, doc = read_settings(target, adapter)
    entries = get_adapter(adapter).hook_configuration(data_dir, mode)["hooks"]
    if host.version is not None:
        doc["version"] = host.version
    hooks = doc.setdefault("hooks", {})
    for name, additions in entries.items():
        existing = hooks.setdefault(name, [])
        if not isinstance(existing, list):
            raise ValueError(f"Existing {name} hooks are not an array.")
        for entry in additions:
            if entry not in existing:
                existing.append(entry)
    return ConnectionPlan(
        workspace, target, previous, json.dumps(doc, indent=2) + "\n", entries, mode, adapter
    )


def receipt_path(data_dir: Path, workspace: Path, adapter: str = "claude-code") -> Path:
    workspace_host(adapter)
    key = hashlib.sha256(os.path.normcase(str(workspace)).encode()).hexdigest()
    # Preserve the receipt location used by the already distributed Claude connection.
    prefix = "" if adapter == "claude-code" else adapter + "-"
    return data_dir / "connections" / f"{prefix}{key}.json"


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
    target = target_for(plan.workspace, plan.adapter)
    previous, previous_doc = read_settings(target, plan.adapter)
    if previous != plan.previous or target != plan.target:
        raise ValueError("Settings changed since review. Open Connect again to refresh.")
    receipt = receipt_path(data_dir, plan.workspace, plan.adapter)
    old_entries: dict[str, Any] = {}
    if receipt.exists():
        old = json.loads(receipt.read_text())
        if old["mode"] != plan.mode:
            raise ValueError("Disconnect this workspace before changing its permission mode.")
        old_entries = old["entries"]
    owned = {}
    for name, additions in plan.entries.items():
        entries = [
            entry
            for entry in additions
            if (
                entry not in previous_doc.get("hooks", {}).get(name, [])
                or entry in old_entries.get(name, [])
            )
        ]
        if entries:
            owned[name] = entries
    target.parent.mkdir(exist_ok=True)
    backup = ""
    if previous is not None:
        backup_path = target.with_name(f"{target.name}.scrip-backup-{uuid4().hex}")
        private_write(backup_path, previous.decode("utf-8-sig"))
        backup = str(backup_path)
    # Record recovery details before changing host configuration.
    record = json.dumps(
        {
            "workspace": str(plan.workspace),
            "adapter": plan.adapter,
            "mode": plan.mode,
            "entries": owned,
            "expected": plan.entries,
            "backup": backup,
        },
        indent=2,
    )
    receipt.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_settings(receipt, record)
    atomic_settings(target, plan.content)


def disconnect(workspace: Path, data_dir: Path, adapter: str = "claude-code") -> None:
    target = target_for(workspace, adapter)
    receipt = receipt_path(data_dir, workspace, adapter)
    record = json.loads(receipt.read_text())
    if not target.exists():
        receipt.unlink()
        return
    _, doc = read_settings(target, adapter)
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


def connection_status(data_dir: Path) -> list[ConnectionStatus]:
    result = []
    for receipt in sorted((data_dir / "connections").glob("*.json")):
        try:
            record = json.loads(receipt.read_text())
            # Pre-multi-host receipts describe Claude Code, which was the only guided host.
            adapter = record.get("adapter", "claude-code")
            workspace = Path(record["workspace"])
            target = target_for(workspace, adapter)
            _, doc = read_settings(target, adapter)
            hooks = doc.get("hooks", {})
            valid = all(
                isinstance(hooks.get(name), list) and all(entry in hooks[name] for entry in entries)
                for name, entries in record.get("expected", record["entries"]).items()
            )
            result.append(
                ConnectionStatus(
                    str(workspace),
                    adapter,
                    record["mode"],
                    "Configured" if valid else "Needs repair",
                )
            )
        except (ValueError, OSError, KeyError, TypeError):
            result.append(ConnectionStatus(str(receipt), "unknown", "unknown", "Needs repair"))
    return result
