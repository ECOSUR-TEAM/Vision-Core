import json

from vision_core.core.contracts.persistence.zone_repository import ZoneRepository
from vision_core.core.infrastructure.persistence.connection import Database
from vision_core.core.infrastructure.persistence.utc import utc_text


class SqliteZoneRepository(ZoneRepository):
    def __init__(self, database: Database):
        self._database = database

    def save(self, name: str, points: tuple[tuple[float, float], ...], updated_at: float) -> bool:
        payload = json.dumps([[float(x), float(y)] for x, y in points])
        connection = self._database.connection()
        with self._database.lock, connection:
            cursor = connection.execute(
                "INSERT INTO zones(name, points_json, updated_at_utc, created_at_utc) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET points_json = excluded.points_json, "
                "updated_at_utc = excluded.updated_at_utc",
                (name, payload, float(updated_at), utc_text()),
            )
        return bool(cursor.rowcount)

    def list(self) -> tuple[tuple[str, tuple[tuple[float, float], ...], float], ...]:
        connection = self._database.connection()
        with self._database.lock:
            rows = connection.execute("SELECT name, points_json, updated_at_utc FROM zones ORDER BY name").fetchall()
        return tuple(
            (
                row["name"],
                tuple((float(x), float(y)) for x, y in json.loads(row["points_json"])),
                float(row["updated_at_utc"]),
            )
            for row in rows
        )

    def delete_older_than(self, timestamp: float) -> int:
        connection = self._database.connection()
        with self._database.lock, connection:
            cursor = connection.execute("DELETE FROM zones WHERE updated_at_utc < ?", (timestamp,))
        return int(cursor.rowcount)
