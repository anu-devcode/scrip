"""Composition root: the only place application code is wired to concrete persistence."""

from pathlib import Path

from .models import utc_now
from .ports import Clock
from .service import CompanionService
from .storage.database import SqliteDatabase


def create_service(database: Path, *, clock: Clock = utc_now) -> CompanionService:
    return CompanionService(SqliteDatabase(database), clock=clock)
