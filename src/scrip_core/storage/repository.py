"""SQL queries and row validation; business decisions belong in CompanionService."""

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta

from ..errors import ConflictError
from ..limits import MAX_QUERY_ITEMS
from ..models import EVENT, Event, IngestResult, InputRequested, Rule, SessionEvent, ToolRequested
from ..ports import SessionKey
from ..records import (
    CoreStatus,
    HistoryEntry,
    NotificationRecord,
    RequestDetails,
    RequestRecord,
    SessionRecord,
)

NOTIFICATION_COLUMNS = "id,event_id,kind,title,state,created_at,delivered_at,attempts,last_error"


class SqliteRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def expire(self, now: datetime) -> None:
        affected = self.connection.execute(
            "SELECT DISTINCT adapter,session_id FROM requests "
            "WHERE status='pending' AND expires_at<=?",
            (now.isoformat(),),
        ).fetchall()
        self.connection.execute(
            "UPDATE requests SET status='expired' WHERE status='pending' AND expires_at<=?",
            (now.isoformat(),),
        )
        self._dismiss_notifications()
        for row in affected:
            self.refresh_session((row["adapter"], row["session_id"]))

    def _dismiss_notifications(self) -> None:
        self.connection.execute("""UPDATE notifications SET state='dismissed',delivery_token=NULL,
            lease_until=NULL WHERE state IN ('queued','delivering','failed') AND EXISTS
            (SELECT 1 FROM requests r WHERE r.event_id=notifications.event_id
             AND r.status IN ('expired','acknowledged','resolved'))""")

    def event(self, event_id: str, fingerprint: str) -> IngestResult | None:
        row = self.connection.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        if row is None:
            return None
        if row["fingerprint"] != fingerprint:
            raise ConflictError("Event ID was already used for different content")
        return IngestResult.model_validate_json(row["result"])

    def record_event(self, event: Event, result: IngestResult, now: datetime) -> None:
        self.connection.execute(
            "INSERT INTO events VALUES(?,?,?,?,?)",
            (
                event.event_id,
                event.fingerprint(),
                event.model_dump_json(),
                result.model_dump_json(),
                now.isoformat(),
            ),
        )

    def session(self, key: SessionKey) -> SessionRecord | None:
        row = self.connection.execute(
            "SELECT * FROM sessions WHERE adapter=? AND id=?",
            key,
        ).fetchone()
        return SessionRecord.model_validate(dict(row)) if row else None

    def update_session(self, event: Event, state: str, now: datetime) -> None:
        model = event.payload.model_name if isinstance(event, SessionEvent) else None
        self.connection.execute(
            """INSERT INTO sessions VALUES(?,?,?,?,?,?)
            ON CONFLICT(adapter,id) DO UPDATE SET state=excluded.state,
            model_name=COALESCE(excluded.model_name,sessions.model_name),
            updated_at=excluded.updated_at""",
            (
                event.adapter,
                event.session_id,
                event.workspace,
                state,
                model,
                now.isoformat(),
            ),
        )

    def refresh_session(self, key: SessionKey) -> None:
        self.connection.execute(
            """UPDATE sessions SET state=CASE
            WHEN EXISTS(SELECT 1 FROM requests r WHERE r.adapter=sessions.adapter
                AND r.session_id=sessions.id AND r.status='pending' AND r.kind='input')
                THEN 'waiting_input'
            WHEN EXISTS(SELECT 1 FROM requests r WHERE r.adapter=sessions.adapter
                AND r.session_id=sessions.id AND r.status='pending') THEN 'waiting_permission'
            ELSE 'running' END
            WHERE adapter=? AND id=? AND state IN ('running','waiting_input','waiting_permission')
            """,
            key,
        )

    def matching_rules(self, event: ToolRequested) -> list[Rule]:
        rows = self.connection.execute(
            "SELECT document FROM rules WHERE adapter=? AND workspace=? AND tool=? ORDER BY id",
            (event.adapter, event.workspace, event.payload.name),
        )
        return [Rule.model_validate_json(row[0]) for row in rows]

    def paused(self) -> bool:
        row = self.connection.execute("SELECT value FROM settings WHERE key='paused'").fetchone()
        return bool(row and row[0] == "true")

    def request(
        self,
        event: ToolRequested | InputRequested,
        kind: str,
        summary: str,
        now: datetime,
        ttl: timedelta,
    ) -> str:
        request_id = hashlib.sha256(event.event_id.encode()).hexdigest()[:32]
        self.connection.execute(
            """INSERT INTO requests(id,event_id,operation_id,adapter,
            session_id,workspace,kind,summary,status,created_at,expires_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                request_id,
                event.event_id,
                event.operation_id,
                event.adapter,
                event.session_id,
                event.workspace,
                kind,
                summary,
                "pending",
                now.isoformat(),
                (now + ttl).isoformat(),
            ),
        )
        title = "An agent needs your input" if kind == "input" else "An agent needs approval"
        self.notify(event.event_id, kind, title, now)
        return request_id

    def resolve_operation(self, key: SessionKey, operation_id: str) -> None:
        self.connection.execute(
            """UPDATE requests SET status='resolved' WHERE adapter=?
            AND session_id=? AND operation_id=? AND status='pending'""",
            (*key, operation_id),
        )
        self._dismiss_notifications()

    def close_requests(self, key: SessionKey) -> None:
        self.connection.execute(
            """UPDATE requests SET status='expired'
            WHERE adapter=? AND session_id=? AND status='pending'""",
            key,
        )
        self._dismiss_notifications()

    def notify(self, event_id: str, kind: str, title: str, now: datetime) -> None:
        identifier = hashlib.sha256(("notification/" + event_id).encode()).hexdigest()[:32]
        self.connection.execute(
            """INSERT INTO notifications
            (id,event_id,kind,title,state,created_at) VALUES(?,?,?,?,?,?)""",
            (
                identifier,
                event_id,
                kind,
                title,
                "queued",
                now.isoformat(),
            ),
        )

    def inbox(self) -> list[RequestRecord]:
        return [
            RequestRecord.model_validate(dict(row))
            for row in self.connection.execute(
                "SELECT * FROM requests WHERE status='pending' ORDER BY created_at LIMIT ?",
                (MAX_QUERY_ITEMS,),
            )
        ]

    def acknowledge(self, request_id: str) -> bool:
        row = self.connection.execute(
            "SELECT adapter,session_id FROM requests WHERE id=? AND status='pending'",
            (request_id,),
        ).fetchone()
        if not row:
            return False
        self.connection.execute(
            "UPDATE requests SET status='acknowledged' WHERE id=?", (request_id,)
        )
        self._dismiss_notifications()
        self.refresh_session((row["adapter"], row["session_id"]))
        return True

    def request_details(self, request_id: str) -> RequestDetails | None:
        row = self.connection.execute(
            """SELECT r.*,e.document FROM requests r JOIN events e ON e.id=r.event_id
            WHERE r.id=? AND r.status='pending'""",
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        request = dict(row)
        event = json.loads(request.pop("document"))
        return RequestDetails.model_validate({"request": request, "event": event})

    def sessions(self) -> list[SessionRecord]:
        return [
            SessionRecord.model_validate(dict(row))
            for row in self.connection.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (MAX_QUERY_ITEMS,),
            )
        ]

    def history(self, limit: int) -> list[HistoryEntry]:
        return [
            HistoryEntry(
                event=EVENT.validate_json(row[0]),
                result=IngestResult.model_validate_json(row[1]),
            )
            for row in self.connection.execute(
                "SELECT document,result FROM events ORDER BY created_at DESC,id LIMIT ?",
                (limit,),
            )
        ]

    def rules(self) -> list[Rule]:
        return [
            Rule.model_validate_json(row[0])
            for row in self.connection.execute(
                "SELECT document FROM rules ORDER BY id",
            )
        ]

    def put_rule(self, rule: Rule) -> None:
        self.connection.execute(
            """INSERT INTO rules(id,document,adapter,workspace,tool)
            VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET document=excluded.document,
            adapter=excluded.adapter,workspace=excluded.workspace,tool=excluded.tool""",
            (
                rule.id,
                rule.model_dump_json(),
                rule.adapter,
                rule.workspace,
                rule.tool,
            ),
        )

    def remove_rule(self, rule_id: str) -> bool:
        return self.connection.execute("DELETE FROM rules WHERE id=?", (rule_id,)).rowcount == 1

    def set_paused(self, paused: bool) -> None:
        self.connection.execute(
            """INSERT INTO settings VALUES('paused',?) ON CONFLICT(key)
            DO UPDATE SET value=excluded.value""",
            ("true" if paused else "false",),
        )

    def status(self) -> CoreStatus:
        return CoreStatus(
            paused=self.paused(),
            events=self.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            rules=self.connection.execute("SELECT COUNT(*) FROM rules").fetchone()[0],
        )

    def notifications(self) -> list[NotificationRecord]:
        rows = self.connection.execute(
            f"SELECT {NOTIFICATION_COLUMNS} FROM notifications ORDER BY created_at DESC LIMIT ?",
            (MAX_QUERY_ITEMS,),
        )
        return [NotificationRecord.model_validate(dict(row)) for row in rows]

    def claim_notifications(
        self,
        token: str,
        now: datetime,
        lease: timedelta,
        limit: int,
    ) -> list[NotificationRecord]:
        rows = self.connection.execute(
            """SELECT id FROM notifications WHERE state='queued'
            OR (state='delivering' AND lease_until<=?) ORDER BY created_at LIMIT ?""",
            (now.isoformat(), limit),
        ).fetchall()
        claimed = []
        for row in rows:
            self.connection.execute(
                """UPDATE notifications SET state='delivering',delivery_token=?,
                lease_until=?,attempts=attempts+1,last_error=NULL WHERE id=?""",
                (token, (now + lease).isoformat(), row["id"]),
            )
            document = self.connection.execute(
                f"SELECT {NOTIFICATION_COLUMNS} FROM notifications WHERE id=?",
                (row["id"],),
            ).fetchone()
            claimed.append(NotificationRecord.model_validate(dict(document)))
        return claimed

    def retry_notification(self, notification_id: str) -> bool:
        return (
            self.connection.execute(
                """UPDATE notifications SET state='queued',last_error=NULL,
            delivery_token=NULL,lease_until=NULL WHERE id=? AND state='failed'
            AND EXISTS (SELECT 1 FROM requests r WHERE r.event_id=notifications.event_id
                        AND r.status='pending')""",
                (notification_id,),
            ).rowcount
            == 1
        )

    def finish_notification(
        self,
        notification_id: str,
        token: str,
        now: datetime,
        error: str | None,
    ) -> None:
        self.connection.execute(
            """UPDATE notifications SET state=?,delivered_at=?,last_error=?,
            delivery_token=NULL,lease_until=NULL WHERE id=? AND state='delivering'
            AND delivery_token=?""",
            (
                "failed" if error else "delivered",
                None if error else now.isoformat(),
                error,
                notification_id,
                token,
            ),
        )

    def release_notification(self, notification_id: str, token: str) -> None:
        self.connection.execute(
            """UPDATE notifications SET state='queued',delivery_token=NULL,lease_until=NULL
            WHERE id=? AND state='delivering' AND delivery_token=?""",
            (notification_id, token),
        )
