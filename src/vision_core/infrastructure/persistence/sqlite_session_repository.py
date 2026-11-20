from vision_core.domain.repositories.session_repository import SessionRepository
from vision_core.infrastructure.persistence.connection import Database
from vision_core.infrastructure.persistence.utc import utc_text


class SqliteSessionRepository(SessionRepository):
    def __init__(self, database: Database):
        self._database = database

    def start(self, session_id: str, started_at: float, camera_id: str | None = None) -> bool:
        connection = self._database.connection()
        with self._database.lock, connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO sessions(session_id, started_at_utc, camera_id, created_at_utc) "
                "VALUES (?, ?, ?, ?)",
                (session_id, float(started_at), camera_id, utc_text()),
            )
        return bool(cursor.rowcount)

    def finish(self, session_id: str, finished_at: float) -> bool:
        connection = self._database.connection()
        with self._database.lock, connection:
            cursor = connection.execute(
                "UPDATE sessions SET finished_at_utc = ? WHERE session_id = ? AND finished_at_utc IS NULL",
                (float(finished_at), session_id),
            )
        return bool(cursor.rowcount)

    def list(
        self, *, since: float | None = None, limit: int | None = None
    ) -> tuple[tuple[str, float, float | None, str | None], ...]:
        query = "SELECT session_id, started_at_utc, finished_at_utc, camera_id FROM sessions WHERE 1 = 1"
        params: list[object] = []
        if since is not None:
            query += " AND started_at_utc >= ?"
            params.append(since)
        query += " ORDER BY started_at_utc, session_id"
        if limit is not None:
            query += " LIMIT ?"
            params.append(max(0, int(limit)))
        connection = self._database.connection()
        with self._database.lock:
            rows = connection.execute(query, params).fetchall()
        return tuple(
            (
                row["session_id"],
                float(row["started_at_utc"]),
                None if row["finished_at_utc"] is None else float(row["finished_at_utc"]),
                row["camera_id"],
            )
            for row in rows
        )

    def delete_older_than(self, timestamp: float) -> int:
        connection = self._database.connection()
        with self._database.lock, connection:
            cursor = connection.execute("DELETE FROM sessions WHERE started_at_utc < ?", (timestamp,))
        return int(cursor.rowcount)
