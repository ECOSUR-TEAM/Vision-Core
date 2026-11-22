from vision_core.core.contracts.persistence.metrics_repository import MetricsRepository
from vision_core.core.infrastructure.persistence.connection import Database
from vision_core.core.infrastructure.persistence.utc import utc_text


class SqliteMetricsRepository(MetricsRepository):
    def __init__(self, database: Database):
        self._database = database

    def record(self, session_id: str, name: str, value: float, timestamp: float) -> bool:
        connection = self._database.connection()
        with self._database.lock, connection:
            cursor = connection.execute(
                "INSERT INTO metrics(session_id, name, value, timestamp_utc, created_at_utc) VALUES (?, ?, ?, ?, ?)",
                (session_id, name, float(value), float(timestamp), utc_text()),
            )
        return bool(cursor.rowcount)

    def list(
        self, *, session_id: str | None = None, since: float | None = None
    ) -> tuple[tuple[str, str, float, float], ...]:
        query = "SELECT session_id, name, value, timestamp_utc FROM metrics WHERE 1 = 1"
        params: list[object] = []
        if session_id is not None:
            query += " AND session_id = ?"
            params.append(session_id)
        if since is not None:
            query += " AND timestamp_utc >= ?"
            params.append(since)
        query += " ORDER BY timestamp_utc, id"
        connection = self._database.connection()
        with self._database.lock:
            rows = connection.execute(query, params).fetchall()
        return tuple((row["session_id"], row["name"], float(row["value"]), float(row["timestamp_utc"])) for row in rows)

    def delete_older_than(self, timestamp: float) -> int:
        connection = self._database.connection()
        with self._database.lock, connection:
            cursor = connection.execute("DELETE FROM metrics WHERE timestamp_utc < ?", (timestamp,))
        return int(cursor.rowcount)
