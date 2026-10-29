from datetime import UTC, datetime, timedelta

import pytest

from scrip_core.bootstrap import create_service
from scrip_core.models import Input, InputRequested, Question, Tool, ToolRequested
from scrip_core.storage.database import SqliteDatabase


class ManualClock:
    def __init__(self):
        self.now = datetime(2026, 10, 28, tzinfo=UTC)

    def __call__(self):
        return self.now

    def advance(self, **delta):
        self.now += timedelta(**delta)


@pytest.fixture
def clock():
    return ManualClock()


@pytest.fixture
def database(tmp_path):
    return SqliteDatabase(tmp_path / "state" / "scrip.sqlite3")


@pytest.fixture
def companion(database, clock):
    return create_service(database.path, clock=clock)


@pytest.fixture
def tool_event(tmp_path):
    return ToolRequested(
        event_id="tool-1",
        operation_id="operation-1",
        adapter="antigravity",
        session_id="session-1",
        workspace=str(tmp_path),
        kind="tool.requested",
        payload=Tool(
            name="run_command", arguments={"CommandLine": "npm test", "Cwd": str(tmp_path)}
        ),
    )


@pytest.fixture
def input_event(tmp_path):
    return InputRequested(
        event_id="question-1",
        operation_id="question-operation-1",
        adapter="antigravity",
        session_id="session-1",
        workspace=str(tmp_path),
        kind="input.requested",
        payload=Input(source_tool="ask_question", questions=[Question(text="Which database?")]),
    )
