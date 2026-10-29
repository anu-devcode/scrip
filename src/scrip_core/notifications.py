from collections.abc import Callable

from .records import NotificationRecord


class ConsoleSink:
    """Development consumer; desktop integrations implement the same send boundary."""

    def __init__(self, emit: Callable[[str], object] = print) -> None:
        self.emit = emit

    def send(self, notification: NotificationRecord) -> None:
        self.emit(f"Scrip: {notification.title} ({notification.id})")
