import json

from vision_core.domain.repositories.track_repository import TrackRepository
from vision_core.infrastructure.persistence.connection import Database
from vision_core.infrastructure.persistence.utc import utc_text


def _decode_bbox(raw: object) -> tuple[float, float, float, float]:
    values = tuple(float(value) for value in json.loads(str(raw)))
    if len(values) != 4:
        raise ValueError("bbox inválido")
    return values[0], values[1], values[2], values[3]


class SqliteTrackRepository(TrackRepository):
    def __init__(self, database: Database):
        self._database = database

    def append(
        self,
        session_id: str,
        track_id: int,
        person_id: str,
        bbox: tuple[float, float, float, float],
        timestamp: float,
    ) -> bool:
        connection = self._database.connection()
        with self._database.lock, connection:
            cursor = connection.execute(
                "INSERT INTO tracks(session_id, track_id, person_id, bbox_json, timestamp_utc, created_at_utc) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    int(track_id),
                    person_id,
                    json.dumps([float(value) for value in bbox]),
                    float(timestamp),
                    utc_text(),
                ),
            )
        return bool(cursor.rowcount)

    def list(
        self,
        *,
        session_id: str | None = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> tuple[tuple[str, int, str, tuple[float, float, float, float], float], ...]:
        query = "SELECT session_id, track_id, person_id, bbox_json, timestamp_utc FROM tracks WHERE 1 = 1"
        params: list[object] = []
        if session_id is not None:
            query += " AND session_id = ?"
            params.append(session_id)
        if since is not None:
            query += " AND timestamp_utc >= ?"
            params.append(since)
        query += " ORDER BY timestamp_utc, id"
        if limit is not None:
            query += " LIMIT ?"
            params.append(max(0, int(limit)))
        connection = self._database.connection()
        with self._database.lock:
            rows = connection.execute(query, params).fetchall()
        return tuple(
            (
                row["session_id"],
                int(row["track_id"]),
                row["person_id"],
                _decode_bbox(row["bbox_json"]),
                float(row["timestamp_utc"]),
            )
            for row in rows
        )

    def delete_older_than(self, timestamp: float) -> int:
        connection = self._database.connection()
        with self._database.lock, connection:
            cursor = connection.execute("DELETE FROM tracks WHERE timestamp_utc < ?", (timestamp,))
        return int(cursor.rowcount)
