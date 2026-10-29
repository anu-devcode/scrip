import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ..errors import StorageError
from ..ports import Repository
from .migrations import migrate
from .repository import SqliteRepository


class SqliteDatabase:
    """Connection factory and transaction scope for the local single-writer database."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            migrate(connection)
            connection.execute("PRAGMA journal_mode=WAL")

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        try:
            connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        except sqlite3.Error as error:
            raise StorageError("Cannot open local database") from error
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
        except sqlite3.Error as error:
            raise StorageError("Local database operation failed") from error
        finally:
            connection.close()

    @contextmanager
    def transaction(self, *, write: bool = True) -> Iterator[Repository]:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield SqliteRepository(connection)
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
