from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Lock

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
