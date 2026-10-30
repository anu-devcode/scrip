"""Small CLI handlers. Domain decisions are delegated to the application service."""

import argparse
import json
import sys
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .adapters.registry import get_adapter
from .bootstrap import create_service
from .client import Client
from .limits import MAX_QUERY_ITEMS
from .models import EVENT, Rule
from .notifications import ConsoleSink
from .service import CompanionService
from .settings import Settings


def _serialize(value: object) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def output(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False, default=_serialize))


def settings_for(args: argparse.Namespace) -> Settings:
    return Settings(Path(args.data_dir).resolve(), getattr(args, "port", 8765))


def local_service(args: argparse.Namespace) -> CompanionService:
    settings = settings_for(args)
    if not settings.database.exists():
        raise ValueError("Run scrip init with this data directory first")
    return create_service(settings.database)


def initialize(args: argparse.Namespace) -> None:
    settings = settings_for(args)
    settings.initialize()
    connection = settings.data_dir / "connection.json"
    if json.loads(connection.read_text(encoding="utf-8"))["base_url"] != settings.base_url:
        raise ValueError(
            "Configured port differs from connection.json; use a separate data directory"
        )
    service = create_service(settings.database)
    if args.command == "init":
        output(
            {"initialized": True, "data_dir": str(settings.data_dir), "endpoint": settings.base_url}
        )
        return
    import uvicorn

    from .api import create_app

    print(f"Scrip listening on {settings.base_url}; state: {settings.data_dir}", file=sys.stderr)
    uvicorn.run(
        create_app(service, settings.token()),
        host="127.0.0.1",
        port=settings.port,
        access_log=False,
        log_level="warning",
    )


def query(args: argparse.Namespace) -> None:
    client = Client(settings_for(args))
    if args.command == "acknowledge":
        if not args.request_id.isalnum():
            raise ValueError("Invalid request ID")
        output(client.request(f"/v1/inbox/{args.request_id}/acknowledge", {}))
        return
    endpoint = "/v1/health" if args.command == "status" else f"/v1/{args.command}"
    if args.command == "history":
        endpoint += f"?limit={max(1, min(args.limit, MAX_QUERY_ITEMS))}"
    output(client.request(endpoint))


def rules(args: argparse.Namespace) -> None:
    service = local_service(args)
    if args.rule_command == "list":
        output(service.rules())
    elif args.rule_command == "add":
        rule = Rule.model_validate_json(args.file.read_text(encoding="utf-8"))
        service.put_rule(rule)
        output({"saved": rule.id})
    else:
        output({"removed": service.remove_rule(args.id)})


def pause(args: argparse.Namespace) -> None:
    service = local_service(args)
    service.set_paused(args.command == "pause")
    output(service.status())


def notifications(args: argparse.Namespace) -> None:
    service = local_service(args)
    if args.drain_console:
        report = service.deliver_notifications(ConsoleSink())
        output(report)
    else:
        output({"items": service.notifications(), "backend": "outbox; console consumer available"})


def schema(args: argparse.Namespace) -> None:
    document = EVENT.json_schema()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        output({"schema": str(args.output.resolve())})
    else:
        output(document)


def adapter(args: argparse.Namespace) -> None:
    host = get_adapter(args.adapter)
    output(
        host.CAPABILITIES
        if args.action == "capabilities"
        else host.hook_configuration(settings_for(args).data_dir, args.mode)
    )


def desktop(args: argparse.Namespace) -> None:
    if find_spec("PySide6") is None:
        raise ValueError(
            "Desktop requires Python 3.12–3.15 and the desktop extra: "
            "uv sync --locked --extra desktop"
        )
    from .desktop.app import run

    raise SystemExit(run(settings_for(args).data_dir))


def diagnostics(args: argparse.Namespace) -> None:
    from .desktop.diagnostics import check

    check(settings_for(args).data_dir)
