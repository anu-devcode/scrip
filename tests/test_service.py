from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest

from scrip_core.bootstrap import create_service
from scrip_core.errors import ConflictError
from scrip_core.models import SessionEvent, ToolCompleted, ToolResult, utc_now
from scrip_core.notifications import ConsoleSink
from tests.factories import rule_for


def test_snapshot_uses_one_transaction_and_expires_consistently(companion, clock, input_event):
    companion.ingest(input_event)
    clock.advance(minutes=16)
    underlying = companion.uow

    class CountingUnitOfWork:
        calls = 0

        @contextmanager
        def transaction(self, *, write=True):
            self.calls += 1
            with underlying.transaction(write=write) as repository:
                yield repository

    counted = CountingUnitOfWork()
    companion.uow = counted
    snapshot = companion.snapshot()
    assert counted.calls == 1
    assert snapshot.status.events == 1
    assert snapshot.requests == ()
    assert snapshot.sessions[0].state == "running"
    assert snapshot.notifications[0].state == "dismissed"


def test_duplicate_input_survives_restart_without_duplicate_notifications(
    companion, database, clock, input_event
):
    first = companion.ingest(input_event)
    assert first.decision.action == "ask"
    restarted = create_service(database.path, clock=clock)
    second = restarted.ingest(input_event)
    assert second.duplicate
    assert second.request_id == first.request_id
    assert len(restarted.inbox()) == 1
    assert len(restarted.notifications()) == 1
    assert len(restarted.history()) == 1
    assert restarted.sessions()[0].state == "waiting_input"


def test_same_id_with_changed_content_conflicts_and_rolls_back(companion, tool_event):
    companion.ingest(tool_event)
    with pytest.raises(ConflictError):
        companion.ingest(tool_event.model_copy(update={"operation_id": "different-action"}))
    assert len(companion.history()) == 1


def test_parallel_retries_create_one_inbox_item(companion, input_event):
    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(lambda _: companion.ingest(input_event), range(16)))
    assert sum(not result.duplicate for result in results) == 1
    assert len(companion.inbox()) == len(companion.notifications()) == 1


def test_approval_is_issued_once_even_after_restart_or_pause(
    companion, database, clock, tool_event
):
    companion.put_rule(rule_for(tool_event))
    assert companion.ingest(tool_event).decision.action == "allow"
    companion.set_paused(True)
    restarted = create_service(database.path, clock=clock)
    assert restarted.ingest(tool_event).decision.action == "ask"
    companion.set_paused(False)
    assert companion.ingest(tool_event).decision.action == "ask"


def test_workspace_cannot_be_swapped_with_same_session_id(companion, tool_event, tmp_path):
    companion.ingest(tool_event)
    with pytest.raises(ConflictError, match="workspace identity"):
        companion.ingest(
            tool_event.model_copy(
                update={
                    "event_id": "tool-2",
                    "workspace": str(tmp_path / "other"),
                }
            )
        )


def test_tool_completion_resolves_only_its_own_input(companion, input_event):
    companion.ingest(input_event)
    other = input_event.model_copy(update={"event_id": "question-2", "operation_id": "operation-2"})
    companion.ingest(other)
    completion = ToolCompleted(
        event_id="post-1",
        operation_id=input_event.operation_id,
        adapter=input_event.adapter,
        session_id=input_event.session_id,
        workspace=input_event.workspace,
        kind="tool.completed",
        payload=ToolResult(name="ask_question", arguments={}),
    )
    companion.ingest(completion)
    assert [item.event_id for item in companion.inbox()] == ["question-2"]
    states = {item.event_id: item.state for item in companion.notifications()}
    assert states == {"question-1": "dismissed", "question-2": "queued"}


def test_acknowledgement_is_not_an_agent_answer(companion, input_event):
    result = companion.ingest(input_event)
    assert companion.acknowledge(result.request_id)
    assert not companion.acknowledge(result.request_id)
    assert companion.inbox() == []
    assert companion.sessions()[0].state == "running"


def test_pending_requests_expire_without_replaying_notification(companion, clock, input_event):
    result = companion.ingest(input_event)
    clock.advance(minutes=16)
    assert companion.inbox() == []
    assert not companion.acknowledge(result.request_id)
    companion.ingest(input_event.model_copy(update={"occurred_at": utc_now()}))
    assert companion.notifications()[0].state == "dismissed"
    assert companion.inbox() == []


def test_stop_dismisses_pending_work_and_blocks_new_tool_until_resume(
    companion, input_event, tool_event
):
    companion.ingest(input_event)
    stop = SessionEvent(
        event_id="stop",
        adapter=input_event.adapter,
        session_id=input_event.session_id,
        workspace=input_event.workspace,
        kind="session.completed",
    )
    companion.ingest(stop)
    assert companion.inbox() == []
    assert companion.sessions()[0].state == "completed"
    with pytest.raises(ConflictError, match="Session is closed"):
        companion.ingest(tool_event)
    companion.ingest(stop.model_copy(update={"kind": "session.started", "event_id": "resume"}))
    assert companion.ingest(tool_event).decision.action == "ask"


def test_console_outbox_does_not_repeat_delivered_items(companion, input_event):
    companion.ingest(input_event)
    messages = []
    assert companion.deliver_notifications(ConsoleSink(messages.append)).delivered == 1
    assert companion.deliver_notifications(ConsoleSink(messages.append)).delivered == 0
    assert len(messages) == 1


def test_observer_does_not_claim_native_approval_is_pending(companion, tool_event):
    event = tool_event.model_copy(update={"policy_mode": "observe"})
    assert companion.ingest(event).decision.action == "ask"
    assert companion.inbox() == []
    assert companion.notifications() == []


def test_next_turn_can_use_same_conversation_without_session_start(companion, tool_event):
    companion.ingest(tool_event)
    companion.ingest(
        SessionEvent(
            event_id="turn-stop",
            adapter=tool_event.adapter,
            session_id=tool_event.session_id,
            workspace=tool_event.workspace,
            kind="turn.completed",
        )
    )
    assert companion.sessions()[0].state == "idle"
    assert companion.inbox() == []
    next_action = tool_event.model_copy(update={"event_id": "next-turn", "operation_id": "next-op"})
    assert companion.ingest(next_action).decision.action == "ask"


@pytest.mark.parametrize("scope", ["session_id", "adapter"])
def test_completion_does_not_cross_session_or_adapter_boundary(companion, input_event, scope):
    companion.ingest(input_event)
    other = input_event.model_copy(update={"event_id": "other-question", scope: "other"})
    companion.ingest(other)
    companion.ingest(
        ToolCompleted(
            event_id="complete-other",
            operation_id=other.operation_id,
            adapter=other.adapter,
            session_id=other.session_id,
            workspace=other.workspace,
            kind="tool.completed",
            payload=ToolResult(name="ask_question"),
        )
    )
    assert [item.event_id for item in companion.inbox()] == [input_event.event_id]


def test_failure_creates_one_generic_alert_without_question_content(companion, input_event):
    companion.ingest(input_event)
    failed = SessionEvent(
        event_id="failure",
        adapter=input_event.adapter,
        session_id=input_event.session_id,
        workspace=input_event.workspace,
        kind="turn.failed",
    )
    companion.ingest(failed)
    companion.ingest(failed)
    failures = [item for item in companion.notifications() if item.kind == "failure"]
    assert len(failures) == 1
    assert failures[0].title == "An agent reported a failure"
    assert companion.sessions()[0].state == "idle"
    assert companion.inbox() == []


def test_request_details_are_not_limited_by_recent_history(companion, input_event):
    result = companion.ingest(input_event)
    for index in range(105):
        companion.ingest(
            SessionEvent(
                event_id=f"progress-{index}",
                adapter=input_event.adapter,
                session_id=input_event.session_id,
                workspace=input_event.workspace,
                kind="session.progress",
            )
        )
    details = companion.request_details(result.request_id)
    assert details.event == input_event
    assert details.request.id == result.request_id
    assert len(companion.history(100)) == 100


def test_request_details_disappear_after_expiry_or_local_dismissal(companion, clock, input_event):
    result = companion.ingest(input_event)
    assert companion.request_details("unknown") is None
    assert companion.acknowledge(result.request_id)
    assert companion.request_details(result.request_id) is None
    second = companion.ingest(
        input_event.model_copy(
            update={
                "event_id": "next-question",
                "operation_id": "next-operation",
            }
        )
    )
    clock.advance(minutes=16)
    assert companion.request_details(second.request_id) is None
