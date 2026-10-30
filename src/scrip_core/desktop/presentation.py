"""Plain text presentation shared by the desktop window and its tests."""

import json
from dataclasses import dataclass

from ..models import InputRequested, Rule
from ..records import CoreStatus, RequestDetails, RequestRecord, SessionRecord


@dataclass(frozen=True)
class DesktopSnapshot:
    status: CoreStatus
    requests: tuple[RequestRecord, ...]
    sessions: tuple[SessionRecord, ...]
    rules: tuple[Rule, ...] = ()


def request_text(details: RequestDetails) -> str:
    event = details.event
    if isinstance(event, InputRequested):
        sections = []
        for index, question in enumerate(event.payload.questions, start=1):
            text = f"{index}. {question.text}"
            if question.options:
                mode = "Choose one or more" if question.multiple else "Choose one"
                text += f"\n\n{mode}:\n" + "\n".join(f"  • {item}" for item in question.options)
            sections.append(text)
        return "\n\n".join(sections)
    arguments = json.dumps(event.payload.arguments, indent=2, ensure_ascii=False, allow_nan=False)
    return f"Tool: {event.payload.name}\n\nExact arguments\n{arguments}"
