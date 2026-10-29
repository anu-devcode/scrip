import sqlite3

import pytest

from scrip_core.bootstrap import create_service
from scrip_core.storage.database import SqliteDatabase
from scrip_core.storage.migrations import MIGRATIONS, initial_schema, operation_identity
from tests.factories import rule_for


def old_database(path):
    connection = sqlite3.connect(path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    initial_schema(connection)
    operation_identity(connection)
    connection.execute("PRAGMA user_version=2")
    return connection


def test_migration_preserves_rules_and_populates_search_columns(tmp_path, tool_event):
    path = tmp_path / "v2.sqlite3"
    rule = rule_for(tool_event)
    with old_database(path) as connection:
        connection.execute("INSERT INTO rules VALUES(?,?)", (rule.id, rule.model_dump_json()))
        connection.execute("INSERT INTO settings VALUES('paused','true')")
    connection.close()
    companion = create_service(path)
    assert companion.rules() == [rule]
    assert companion.status().paused
    companion.set_paused(False)
    assert companion.ingest(tool_event).decision.action == "allow"
    assert create_service(path).status().events == 1


def test_failed_migration_rolls_back_schema_and_version(tmp_path):
    path = tmp_path / "broken-v2.sqlite3"
    with old_database(path) as connection:
        connection.execute("INSERT INTO rules VALUES('invalid','{}')")
    connection.close()
    with pytest.raises(KeyError):
        SqliteDatabase(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        columns = {row[1] for row in connection.execute("PRAGMA table_info(notifications)")}
        assert "delivery_token" not in columns


def test_newer_database_is_refused_without_changing_it(tmp_path):
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(f"PRAGMA user_version={len(MIGRATIONS) + 1}")
    original = path.read_bytes()
    with pytest.raises(ValueError, match="newer Scrip version"):
        SqliteDatabase(path)
    assert path.read_bytes() == original


def test_repository_transaction_rolls_back_on_failure(database, tool_event):
    rule = rule_for(tool_event)
    with pytest.raises(RuntimeError), database.transaction() as repository:
        repository.put_rule(rule)
        raise RuntimeError("abort this operation")
    with database.transaction(write=False) as repository:
        assert repository.rules() == []
