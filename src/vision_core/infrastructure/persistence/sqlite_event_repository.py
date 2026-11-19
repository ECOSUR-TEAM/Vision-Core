import json

from vision_core.application.event_serializer import event_to_dict
from vision_core.domain.model.event import Event
from vision_core.domain.repositories.event_repository import EventRepository
from vision_core.infrastructure.persistence.connection import Database
from vision_core.infrastructure.persistence.event_identity import event_id_for
from vision_core.infrastructure.persistence.utc import utc_text


class SqliteEventRepository(EventRepository):
    def __init__(self, database: Database):
        self._database = database

    def append(self, event: Event, session_id: str | None = None) -> bool:
        payload = event_to_dict(event)
        event_id = event_id_for(event)
        metadata = json.dumps(payload["metadata"], sort_keys=True, ensure_ascii=False, default=str)
        connection = self._database.connection()
        with self._database.lock, connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO events("
                "event_id, event_type, person_id, session_id, timestamp_utc, metadata_json, created_at_utc"
                ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    str(payload["event"]),
                    str(payload["person_id"]),
                    session_id,
                    float(payload["timestamp"]),
                    metadata,
                    utc_text(),
                ),
            )
            if cursor.rowcount:
                connection.execute(
                    "INSERT INTO persons(person_id, first_seen_utc, last_seen_utc, metadata_json, created_at_utc) "
                    "VALUES (?, ?, ?, '{}', ?) "
                    "ON CONFLICT(person_id) DO UPDATE SET last_seen_utc = excluded.last_seen_utc",
                    (
                        str(payload["person_id"]),
                        float(payload["timestamp"]),
                        float(payload["timestamp"]),
                        utc_text(),
                    ),
                )
        return bool(cursor.rowcount)

    def list(
        self,
        *,
        person_id: str | None = None,
        session_id: str | None = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> tuple[Event, ...]:
        query = "SELECT event_id, event_type, person_id, timestamp_utc, metadata_json FROM events WHERE 1 = 1"
        params: list[object] = []
        if person_id is not None:
            query += " AND person_id = ?"
            params.append(person_id)
        if session_id is not None:
            query += " AND session_id = ?"
            params.append(session_id)
        if since is not None:
            query += " AND timestamp_utc >= ?"
            params.append(since)
        query += " ORDER BY timestamp_utc, rowid"
        if limit is not None:
            query += " LIMIT ?"
            params.append(max(0, int(limit)))
        connection = self._database.connection()
        with self._database.lock:
            rows = connection.execute(query, params).fetchall()
        return tuple(
            Event(
                row["event_type"],
                row["person_id"],
                float(row["timestamp_utc"]),
                json.loads(row["metadata_json"]),
                event_id=row["event_id"],
            )
            for row in rows
        )

    def delete_older_than(self, timestamp: float) -> int:
        connection = self._database.connection()
        with self._database.lock, connection:
            cursor = connection.execute("DELETE FROM events WHERE timestamp_utc < ?", (timestamp,))
        return int(cursor.rowcount)
