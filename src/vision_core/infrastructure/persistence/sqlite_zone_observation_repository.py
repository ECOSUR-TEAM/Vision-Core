import json

from vision_core.domain.repositories.zone_observation_repository import ZoneObservationRepository
from vision_core.infrastructure.persistence.connection import Database
from vision_core.infrastructure.persistence.utc import utc_text


class SqliteZoneObservationRepository(ZoneObservationRepository):
    def __init__(self, database: Database):
        self._database = database

    def append(
        self,
        person_id: str,
        zone: str,
        position: tuple[float, float],
        timestamp: float,
        event_id: str | None = None,
    ) -> bool:
        connection = self._database.connection()
        with self._database.lock, connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO zone_observations("
                "event_id, person_id, zone, position_json, timestamp_utc, created_at_utc"
                ") VALUES (?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    person_id,
                    zone,
                    json.dumps([float(position[0]), float(position[1])]),
                    float(timestamp),
                    utc_text(),
                ),
            )
        return bool(cursor.rowcount)

    def list(
        self,
        *,
        person_id: str | None = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> tuple[tuple[str, str, tuple[float, float], float], ...]:
        query = "SELECT person_id, zone, position_json, timestamp_utc FROM zone_observations WHERE 1 = 1"
        params: list[object] = []
        if person_id is not None:
            query += " AND person_id = ?"
            params.append(person_id)
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
                row["person_id"],
                row["zone"],
                tuple(float(value) for value in json.loads(row["position_json"])),
                float(row["timestamp_utc"]),
            )
            for row in rows
        )

    def delete_older_than(self, timestamp: float) -> int:
        connection = self._database.connection()
        with self._database.lock, connection:
            cursor = connection.execute("DELETE FROM zone_observations WHERE timestamp_utc < ?", (timestamp,))
        return int(cursor.rowcount)
