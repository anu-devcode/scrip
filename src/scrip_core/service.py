"""Application orchestration. No SQL, HTTP framework, shell, or host-specific schemas."""

from datetime import datetime, timedelta
from uuid import uuid4

from .authorization import ProjectAuthorization
from .errors import ConflictError, DeliveryDeferred
from .limits import MAX_QUERY_ITEMS
from .models import (
    Decision,
    Event,
    IngestResult,
    InputRequested,
    Rule,
    SessionEvent,
    ToolCompleted,
    ToolRequested,
    utc_now,
)
from .policy import decide
from .ports import Clock, NotificationSink, Repository, UnitOfWork
from .records import (
    CoreSnapshot,
    CoreStatus,
    DeliveryReport,
    HistoryEntry,
    NotificationRecord,
    RequestDetails,
    RequestRecord,
    SessionRecord,
)


class CompanionService:
    def __init__(
        self,
        unit_of_work: UnitOfWork,
        *,
        clock: Clock = utc_now,
        request_ttl: timedelta = timedelta(minutes=15),
    ) -> None:
        if request_ttl <= timedelta():
            raise ValueError("Request lifetime must be positive")
        self.uow = unit_of_work
        self.clock = clock
        self.request_ttl = request_ttl

    def ingest(self, event: Event, *, authorization_id: str | None = None) -> IngestResult:
        now = self.clock()
        with self.uow.transaction() as repository:
            repository.expire(now)
            previous = repository.event(event.event_id, event.fingerprint())
            if previous is not None:
                if (
                    isinstance(event, ToolRequested)
                    and event.policy_mode == "enforce"
                    and previous.decision.action == "allow"
                ):
                    return IngestResult(
                        event_id=event.event_id,
                        duplicate=True,
                        decision=Decision(
                            action="ask",
                            reason=(
                                "Approval already issued for this event; "
                                "review the retry in the host"
                            ),
                        ),
                    )
                return previous.model_copy(update={"duplicate": True})

            key = (event.adapter, event.session_id)
            session = repository.session(key)
            if session and session.workspace != event.workspace:
                raise ConflictError("A session cannot change its workspace identity")
            if (
                session
                and session.state in ("completed", "failed")
                and not (isinstance(event, SessionEvent) and event.kind == "session.started")
            ):
                raise ConflictError("Session is closed; a new session.started event is required")
            state = {
                "session.completed": "completed",
                "session.failed": "failed",
                "turn.completed": "idle",
                "turn.failed": "idle",
            }.get(event.kind, "running")
            repository.update_session(event, state, now)
            decision, request_id = self._handle(repository, event, now, authorization_id)
            if state in ("completed", "failed", "idle"):
                repository.close_requests(key)
                if event.kind in ("session.failed", "turn.failed"):
                    repository.notify(event.event_id, "failure", "An agent reported a failure", now)
            else:
                repository.refresh_session(key)
            result = IngestResult(event_id=event.event_id, decision=decision, request_id=request_id)
            repository.record_event(event, result, now)
            return result

    def _handle(
        self,
        repository: Repository,
        event: Event,
        now: datetime,
        authorization_id: str | None = None,
    ) -> tuple[Decision, str | None]:
        request_id = None
        decision = Decision(action="none", reason="Event recorded")
        if isinstance(event, ToolRequested):
            rules = repository.matching_rules(event)
            authorization = repository.project_authorization() if authorization_id else None
            if authorization is not None and authorization.id == authorization_id:
                rules += authorization.matching_rules(event, now)
            else:
                authorization = None
            decision = decide(
                event, rules, paused=repository.paused(), now=now, authorization=authorization
            )
            if (
                decision.action == "allow"
                and authorization is not None
                and authorization.session is not None
                and authorization.session.session_id is None
                and authorization.session.matches(event)
            ):
                # Binding and approval commit with the event in one transaction. Concurrent
                # conversations cannot both acquire the same active project session grant.
                repository.set_project_authorization(
                    authorization.model_copy(
                        update={
                            "session": authorization.session.model_copy(
                                update={"session_id": event.session_id}
                            )
                        }
                    )
                )
            if decision.action == "ask" and event.policy_mode == "enforce":
                request_id = repository.request(
                    event,
                    "permission",
                    event.payload.name,
                    now,
                    self.request_ttl,
                )
        elif isinstance(event, InputRequested):
            decision = Decision(
                action="ask", reason="Answer this question in the originating agent"
            )
            summary = " ".join(question.text for question in event.payload.questions)[:1000]
            request_id = repository.request(event, "input", summary, now, self.request_ttl)
        elif isinstance(event, ToolCompleted):
            repository.resolve_operation((event.adapter, event.session_id), event.operation_id)
        return decision, request_id

    def project_authorization(self) -> ProjectAuthorization | None:
        with self.uow.transaction(write=False) as repository:
            return repository.project_authorization()

    def set_project_authorization(self, authorization: ProjectAuthorization | None) -> None:
        with self.uow.transaction() as repository:
            repository.set_project_authorization(authorization)

    def activate_project_authorization(
        self, authorization: ProjectAuthorization
    ) -> ProjectAuthorization:
        with self.uow.transaction() as repository:
            current = repository.project_authorization()
            if (
                current is not None
                and current.id == authorization.id
                and current.expires_at > self.clock()
                and current.session is not None
                and authorization.session is not None
                and current.session.adapter == authorization.session.adapter
                and current.session.workspace == authorization.session.workspace
                and current.session.tool == authorization.session.tool
            ):
                return current
            repository.set_project_authorization(authorization)
            return authorization

    def snapshot(self) -> CoreSnapshot:
        """Read one consistent desktop view and expire requests once per refresh."""
        with self.uow.transaction() as repository:
            repository.expire(self.clock())
            return CoreSnapshot(
                repository.status(),
                tuple(repository.inbox()),
                tuple(repository.sessions()),
                tuple(repository.rules()),
                tuple(repository.notifications()),
            )

    def inbox(self) -> list[RequestRecord]:
        with self.uow.transaction() as repository:
            repository.expire(self.clock())
            return repository.inbox()

    def acknowledge(self, request_id: str) -> bool:
        with self.uow.transaction() as repository:
            repository.expire(self.clock())
            return repository.acknowledge(request_id)

    def request_details(self, request_id: str) -> RequestDetails | None:
        with self.uow.transaction() as repository:
            repository.expire(self.clock())
            return repository.request_details(request_id)

    def sessions(self) -> list[SessionRecord]:
        with self.uow.transaction() as repository:
            repository.expire(self.clock())
            return repository.sessions()

    def history(self, limit: int = 50) -> list[HistoryEntry]:
        with self.uow.transaction(write=False) as repository:
            return repository.history(max(1, min(limit, MAX_QUERY_ITEMS)))

    def rules(self) -> list[Rule]:
        with self.uow.transaction(write=False) as repository:
            return repository.rules()

    def put_rule(self, rule: Rule) -> None:
        with self.uow.transaction() as repository:
            repository.put_rule(rule)

    def remove_rule(self, rule_id: str) -> bool:
        with self.uow.transaction() as repository:
            return repository.remove_rule(rule_id)

    def set_paused(self, paused: bool) -> None:
        with self.uow.transaction() as repository:
            repository.set_paused(paused)

    def status(self) -> CoreStatus:
        with self.uow.transaction(write=False) as repository:
            return repository.status()

    def notifications(self) -> list[NotificationRecord]:
        with self.uow.transaction() as repository:
            repository.expire(self.clock())
            return repository.notifications()

    def deliver_notifications(self, sink: NotificationSink, limit: int = 50) -> DeliveryReport:
        token = uuid4().hex
        with self.uow.transaction() as repository:
            repository.expire(self.clock())
            pending = repository.claim_notifications(
                token,
                self.clock(),
                timedelta(seconds=30),
                max(1, min(limit, MAX_QUERY_ITEMS)),
            )
        delivered = failed = 0
        for index, notification in enumerate(pending):
            error = None
            try:
                sink.send(notification)  # External I/O must not hold a database transaction.
                delivered += 1
            except DeliveryDeferred:
                with self.uow.transaction() as repository:
                    for remaining in pending[index:]:
                        repository.release_notification(remaining.id, token)
                return DeliveryReport(
                    delivered=delivered,
                    failed=failed,
                    deferred=len(pending) - index,
                )
            except Exception as exception:
                error = type(exception).__name__
                failed += 1
            with self.uow.transaction() as repository:
                repository.finish_notification(notification.id, token, self.clock(), error)
        return DeliveryReport(delivered=delivered, failed=failed)

    def retry_notification(self, notification_id: str) -> bool:
        """Requeue a failed alert only while its original request still needs attention."""
        with self.uow.transaction() as repository:
            repository.expire(self.clock())
            return repository.retry_notification(notification_id)
