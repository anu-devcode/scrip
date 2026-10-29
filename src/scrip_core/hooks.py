"""Host stdin/stdout boundary. Only validated native JSON responses go to stdout."""

import json
import sys
from pathlib import Path

from .adapters.common import HookMode
from .adapters.registry import get_adapter
from .client import Client
from .limits import MAX_EVENT_BYTES
from .models import Decision
from .settings import Settings


def run_hook(adapter_name: str, event_name: str, mode: HookMode, data_dir: Path) -> int:
    adapter = get_adapter(adapter_name)
    try:
        raw = sys.stdin.buffer.read(MAX_EVENT_BYTES + 1)
        if len(raw) > MAX_EVENT_BYTES:
            raise ValueError("Hook payload is too large")
        payload = json.loads(raw.decode("utf-8-sig"))
        event = adapter.normalize(event_name, payload, mode)
        result = Client(Settings(data_dir)).request("/v1/events", event.model_dump(mode="json"))
        response = adapter.hook_response(
            event_name,
            event,
            Decision.model_validate(result["decision"]),
            mode,
        )
    except Exception as error:
        # Fail conservatively even for unexpected input/transport failures. Do not log secrets.
        print(
            f"Scrip hook could not complete ({type(error).__name__}); no approval granted.",
            file=sys.stderr,
        )
        response = adapter.unavailable_response(event_name, mode)
    print(json.dumps(response, ensure_ascii=False, allow_nan=False))
    return 0
