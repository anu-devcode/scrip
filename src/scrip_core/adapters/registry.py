"""Explicit built-in adapters. Importing the registry performs no host configuration."""

from collections.abc import Mapping
from types import MappingProxyType

from . import antigravity, claude_code
from .common import HookAdapter

_ADAPTERS: Mapping[str, HookAdapter] = MappingProxyType(
    {
        "antigravity": antigravity,
        "claude-code": claude_code,
    }
)


def adapter_names() -> tuple[str, ...]:
    return tuple(_ADAPTERS)


def get_adapter(name: str) -> HookAdapter:
    try:
        return _ADAPTERS[name]
    except KeyError:
        raise ValueError(f"Unsupported adapter: {name}") from None
