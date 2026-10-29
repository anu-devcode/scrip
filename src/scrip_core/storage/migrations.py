"""Forward-only schema migrations, run atomically during application initialization."""

import json
import sqlite3
from collections.abc import Callable


def initial_schema(connection: sqlite3.Connection) -> None:
    statements = (
        """CREATE TABLE sessions (
            adapter TEXT NOT NULL, id TEXT NOT NULL, workspace TEXT NOT NULL,
            state TEXT NOT NULL, model_name TEXT, updated_at TEXT NOT NULL,
            PRIMARY KEY(adapter,id))""",
        """CREATE TABLE events (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
            document TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL)""",
        """CREATE TABLE requests (id TEXT PRIMARY KEY, event_id TEXT UNIQUE NOT NULL,
            adapter TEXT NOT NULL, session_id TEXT NOT NULL, workspace TEXT NOT NULL,
            kind TEXT NOT NULL, summary TEXT NOT NULL, status TEXT NOT NULL,
            created_at TEXT NOT NULL, expires_at TEXT NOT NULL)""",
        """CREATE TABLE notifications (id TEXT PRIMARY KEY, event_id TEXT UNIQUE NOT NULL,
            kind TEXT NOT NULL, title TEXT NOT NULL, state TEXT NOT NULL,
            created_at TEXT NOT NULL, delivered_at TEXT)""",
        "CREATE TABLE rules (id TEXT PRIMARY KEY, document TEXT NOT NULL)",
        "CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
        "CREATE INDEX requests_pending ON requests(status,expires_at)",
    )
    for statement in statements:
        connection.execute(statement)


def operation_identity(connection: sqlite3.Connection) -> None:
    connection.execute("ALTER TABLE requests ADD COLUMN operation_id TEXT")


def indexed_queries_and_delivery_leases(connection: sqlite3.Connection) -> None:
    for declaration in (
        "delivery_token TEXT",
        "lease_until TEXT",
        "attempts INTEGER NOT NULL DEFAULT 0",
        "last_error TEXT",
    ):
        connection.execute(f"ALTER TABLE notifications ADD COLUMN {declaration}")
    for name in ("adapter", "workspace", "tool"):
        connection.execute(f"ALTER TABLE rules ADD COLUMN {name} TEXT")
    for row in connection.execute("SELECT id,document FROM rules").fetchall():
        rule = json.loads(row["document"])
        connection.execute(
            "UPDATE rules SET adapter=?,workspace=?,tool=? WHERE id=?",
            (
                rule["adapter"],
                rule["workspace"],
                rule["tool"],
                row["id"],
            ),
        )
    statements = (
        "CREATE INDEX events_chronology ON events(created_at DESC,id)",
        "CREATE INDEX sessions_updated ON sessions(updated_at DESC)",
        "CREATE INDEX requests_session ON requests(adapter,session_id,status,kind)",
        "CREATE INDEX requests_operation ON requests(adapter,session_id,operation_id,status)",
        "CREATE INDEX notification_delivery ON notifications(state,created_at,lease_until)",
        "CREATE INDEX rules_scope ON rules(adapter,workspace,tool)",
    )
    for statement in statements:
        connection.execute(statement)


MIGRATIONS: tuple[Callable[[sqlite3.Connection], None], ...] = (
    initial_schema,
    operation_identity,
    indexed_queries_and_delivery_leases,
)


def migrate(connection: sqlite3.Connection) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > len(MIGRATIONS):
            raise ValueError("Database was created by a newer Scrip version")
        for index in range(version, len(MIGRATIONS)):
            MIGRATIONS[index](connection)
            connection.execute(f"PRAGMA user_version={index + 1}")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
