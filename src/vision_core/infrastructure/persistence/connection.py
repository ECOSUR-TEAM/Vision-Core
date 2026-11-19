import sqlite3
import threading
from pathlib import Path

from vision_core.infrastructure.persistence.migration_runner import MigrationRunner


class Database:
    def __init__(self, path: str | Path, *, busy_timeout_seconds: float = 5.0, migrate: bool = True):
        self.path = Path(path).expanduser()
        self._busy_timeout_seconds = max(0.0, busy_timeout_seconds)
        self._migrate = migrate
        self._connection: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    def connection(self) -> sqlite3.Connection:
        with self._lock:
            if self._connection is None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                connection = sqlite3.connect(
                    str(self.path), timeout=self._busy_timeout_seconds, check_same_thread=False
                )
                connection.row_factory = sqlite3.Row
                connection.execute(f"PRAGMA busy_timeout = {int(self._busy_timeout_seconds * 1000)}")
                connection.execute("PRAGMA journal_mode = WAL")
                connection.execute("PRAGMA foreign_keys = ON")
                self._connection = connection
                if self._migrate:
                    MigrationRunner(connection).migrate()
            return self._connection

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
