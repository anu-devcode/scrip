from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Lock

import pytest

from scrip_core.errors import DeliveryDeferred
from scrip_core.notifications import ConsoleSink


def test_delivery_does_not_hold_database_transaction(companion, input_event):
    companion.ingest(input_event)

    def emit(_message):
        companion.ingest(
            input_event.model_copy(
                update={
                    "event_id": "new-question",
                    "operation_id": "new-operation",
                }
            )
        )

    assert companion.deliver_notifications(ConsoleSink(emit)).delivered == 1
    assert len(companion.inbox()) == 2
    assert {item.state for item in companion.notifications()} == {"queued", "delivered"}


def test_concurrent_consumers_do_not_claim_same_active_lease(companion, input_event):
    for index in range(10):
        companion.ingest(
            input_event.model_copy(
                update={
                    "event_id": f"question-{index}",
                    "operation_id": f"operation-{index}",
                }
            )
        )
    messages = []
    lock = Lock()

    def emit(message):
        with lock:
            messages.append(message)

    with ThreadPoolExecutor(max_workers=8) as workers:
        reports = list(
            workers.map(
                lambda _: companion.deliver_notifications(ConsoleSink(emit)),
                range(8),
            )
        )
    assert sum(report.delivered for report in reports) == 10
    assert len(set(messages)) == len(messages) == 10
    assert all(item.state == "delivered" for item in companion.notifications())


def test_abandoned_lease_recovers_and_stale_worker_cannot_complete(
    companion,
    database,
    clock,
    input_event,
):
    companion.ingest(input_event)
    with database.transaction() as repository:
        first = repository.claim_notifications("old-worker", clock(), timedelta(seconds=30), 1)
    assert companion.deliver_notifications(ConsoleSink(lambda _: None)).delivered == 0
    clock.advance(seconds=31)
    with database.transaction() as repository:
        second = repository.claim_notifications("new-worker", clock(), timedelta(seconds=30), 1)
        repository.finish_notification(first[0].id, "old-worker", clock(), None)
    assert second[0].attempts == 2
    assert companion.notifications()[0].state == "delivering"
    with database.transaction() as repository:
        repository.finish_notification(second[0].id, "new-worker", clock(), None)
    assert companion.notifications()[0].state == "delivered"
    assert "delivery_token" not in companion.notifications()[0].model_dump()


def test_sink_failure_is_recorded_without_leaking_content_or_blocking_other_items(
    companion,
    input_event,
):
    companion.ingest(input_event)
    companion.ingest(
        input_event.model_copy(
            update={
                "event_id": "second-question",
                "operation_id": "second-operation",
            }
        )
    )
    attempts = []

    def emit(message):
        attempts.append(message)
        if len(attempts) == 1:
            raise OSError("private transport credentials")

    report = companion.deliver_notifications(ConsoleSink(emit))
    assert report.delivered == report.failed == 1
    notifications = companion.notifications()
    assert {item.state for item in notifications} == {"delivered", "failed"}
    assert {item.last_error for item in notifications} == {None, "OSError"}
    assert companion.deliver_notifications(ConsoleSink(emit)).delivered == 0


def test_acknowledgement_during_delivery_cannot_revive_dismissed_item(companion, input_event):
    request = companion.ingest(input_event)
    companion.deliver_notifications(
        ConsoleSink(lambda _: companion.acknowledge(request.request_id))
    )
    assert companion.notifications()[0].state == "dismissed"
    assert companion.inbox() == []


def test_deferring_a_batch_releases_all_unattempted_leases(companion, input_event):
    for index in range(3):
        companion.ingest(
            input_event.model_copy(
                update={
                    "event_id": f"deferred-{index}",
                    "operation_id": f"deferred-op-{index}",
                }
            )
        )
    attempted = []

    def unavailable(message):
        attempted.append(message)
        raise DeliveryDeferred()

    report = companion.deliver_notifications(ConsoleSink(unavailable))
    assert report.deferred == 3
    assert report.delivered == report.failed == 0
    assert len(attempted) == 1
    assert all(item.state == "queued" for item in companion.notifications())
    assert companion.deliver_notifications(ConsoleSink(lambda _: None)).delivered == 3


def test_deferral_does_not_revive_a_dismissed_notification(companion, input_event):
    request = companion.ingest(input_event)

    def closing(_message):
        companion.acknowledge(request.request_id)
        raise DeliveryDeferred()

    assert companion.deliver_notifications(ConsoleSink(closing)).deferred == 1
    assert companion.notifications()[0].state == "dismissed"


def fail_delivery(companion, event):
    companion.ingest(event)

    def unavailable(_message):
        raise OSError("private transport details")

    assert companion.deliver_notifications(ConsoleSink(unavailable)).failed == 1
    return companion.notifications()[0]


def test_failed_pending_alert_can_retry_once_without_replaying_its_event(companion, input_event):
    notification = fail_delivery(companion, input_event)
    original_details = companion.request_details(companion.inbox()[0].id)
    assert companion.retry_notification(notification.id)
    assert not companion.retry_notification(notification.id)
    queued = companion.notifications()[0]
    assert queued.state == "queued"
    assert queued.last_error is None
    assert queued.attempts == 1
    assert companion.request_details(companion.inbox()[0].id) == original_details
    assert companion.status().events == 1
    messages = []
    assert companion.deliver_notifications(ConsoleSink(messages.append)).delivered == 1
    assert len(messages) == 1
    assert companion.notifications()[0].attempts == 2
    assert not companion.retry_notification(notification.id)


@pytest.mark.parametrize("ending", ["dismiss", "expire", "resolve", "close"])
def test_retry_cannot_revive_failed_alert_after_request_ends(companion, input_event, clock, ending):
    from scrip_core.models import SessionEvent, SessionInfo, ToolCompleted, ToolResult

    notification = fail_delivery(companion, input_event)
    if ending == "dismiss":
        companion.acknowledge(companion.inbox()[0].id)
    elif ending == "expire":
        clock.advance(minutes=16)
    elif ending == "resolve":
        companion.ingest(
            ToolCompleted(
                event_id="completed",
                operation_id=input_event.operation_id,
                adapter=input_event.adapter,
                session_id=input_event.session_id,
                workspace=input_event.workspace,
                kind="tool.completed",
                payload=ToolResult(name="ask_question"),
            )
        )
    else:
        companion.ingest(
            SessionEvent(
                event_id="closed",
                adapter=input_event.adapter,
                session_id=input_event.session_id,
                workspace=input_event.workspace,
                kind="session.completed",
                payload=SessionInfo(),
            )
        )
    assert not companion.retry_notification(notification.id)
    assert companion.notifications()[0].state == "dismissed"
    assert companion.deliver_notifications(ConsoleSink(lambda _: None)).delivered == 0


def test_concurrent_retry_only_requeues_once_and_cannot_steal_delivery_lease(
    companion, database, clock, input_event
):
    notification = fail_delivery(companion, input_event)
    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(
            workers.map(lambda _: companion.retry_notification(notification.id), range(8))
        )
    assert sum(results) == 1
    with database.transaction() as repository:
        repository.claim_notifications("active-worker", clock(), timedelta(seconds=30), 1)
    assert not companion.retry_notification(notification.id)
    assert companion.notifications()[0].state == "delivering"
    assert not companion.retry_notification("unknown-notification")


def test_retry_racing_dismissal_cannot_leave_an_alert_queued(companion, input_event):
    notification = fail_delivery(companion, input_event)
    request_id = companion.inbox()[0].id
    with ThreadPoolExecutor(max_workers=2) as workers:
        retry = workers.submit(companion.retry_notification, notification.id)
        dismiss = workers.submit(companion.acknowledge, request_id)
        retry.result()
        assert dismiss.result()
    assert companion.notifications()[0].state == "dismissed"
    assert companion.deliver_notifications(ConsoleSink(lambda _: None)).delivered == 0
