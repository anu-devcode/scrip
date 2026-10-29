"""CLI composition: parse commands and delegate to focused handlers."""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from . import __version__, commands
from .adapters.registry import adapter_names
from .errors import StorageError
from .hooks import run_hook
from .settings import default_data_dir


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="scrip", description="Scrip local agent companion")
    root.add_argument("--version", action="version", version=f"Scrip core {__version__}")
    root.add_argument("--data-dir", type=Path, default=default_data_dir())
    subcommands = root.add_subparsers(dest="command", required=True)
    schema = subcommands.add_parser("schema", help="Export the versioned event contract")
    schema.add_argument("--output", type=Path)
    schema.set_defaults(handler=commands.schema)
    for name in ("init", "serve"):
        command = subcommands.add_parser(name)
        command.add_argument("--port", type=int, default=8765)
        command.set_defaults(handler=commands.initialize)
    for name in ("status", "sessions", "inbox", "history", "acknowledge"):
        command = subcommands.add_parser(name)
        command.set_defaults(handler=commands.query)
        if name == "history":
            command.add_argument("--limit", type=int, default=20)
        elif name == "acknowledge":
            command.add_argument("request_id")
    for name in ("pause", "resume"):
        subcommands.add_parser(name).set_defaults(handler=commands.pause)
    rules = subcommands.add_parser("rules")
    rules.set_defaults(handler=commands.rules)
    actions = rules.add_subparsers(dest="rule_command", required=True)
    actions.add_parser("list")
    actions.add_parser("add").add_argument("file", type=Path)
    actions.add_parser("remove").add_argument("id")
    notifications = subcommands.add_parser("notifications")
    notifications.add_argument("--drain-console", action="store_true")
    notifications.set_defaults(handler=commands.notifications)
    adapter = subcommands.add_parser("adapter")
    adapter.add_argument("action", choices=("capabilities", "config"))
    adapter.add_argument("--adapter", choices=adapter_names(), default="antigravity")
    adapter.add_argument("--mode", choices=("observe", "enforce"), default="observe")
    adapter.set_defaults(handler=commands.adapter)
    hook = subcommands.add_parser("hook", help="Documented stdin/stdout hook adapter")
    hook.add_argument("adapter", choices=adapter_names())
    hook.add_argument("--event", required=True)
    hook.add_argument("--mode", choices=("observe", "enforce"), default="observe")
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "hook":
            return run_hook(args.adapter, args.event, args.mode, args.data_dir.resolve())
        handler: Callable[[argparse.Namespace], None] = args.handler
        handler(args)
        return 0
    except (ValueError, OSError, StorageError) as error:
        print(f"Scrip: {error}", file=sys.stderr)
        return 1
