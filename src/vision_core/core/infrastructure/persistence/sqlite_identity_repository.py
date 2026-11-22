import json

from vision_core.core.contracts.persistence.identity_repository import IdentityRepository
from vision_core.core.domain.types import Embedding
from vision_core.core.infrastructure.persistence.connection import Database
from vision_core.core.infrastructure.persistence.utc import utc_text


class SqliteIdentityRepository(IdentityRepository):
    def __init__(self, database: Database):
        self._database = database

    def save(self, person_id: str, embedding: Embedding, last_seen_at: float) -> bool:
        values = [float(component) for component in embedding]
        connection = self._database.connection()
        with self._database.lock, connection:
            cursor = connection.execute(
                "INSERT INTO identity_gallery(person_id, embedding_json, last_seen_at_utc, created_at_utc) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(person_id) DO UPDATE SET "
                "embedding_json = excluded.embedding_json, last_seen_at_utc = excluded.last_seen_at_utc",
                (person_id, json.dumps(values), float(last_seen_at), utc_text()),
            )
            connection.execute(
                "INSERT INTO persons(person_id, first_seen_utc, last_seen_utc, metadata_json, created_at_utc) "
                "VALUES (?, ?, ?, '{}', ?) "
                "ON CONFLICT(person_id) DO UPDATE SET last_seen_utc = excluded.last_seen_utc",
                (person_id, float(last_seen_at), float(last_seen_at), utc_text()),
            )
        return bool(cursor.rowcount)

    def list_active(self, *, since: float) -> tuple[tuple[str, tuple[float, ...], float], ...]:
        connection = self._database.connection()
        with self._database.lock:
            rows = connection.execute(
                "SELECT person_id, embedding_json, last_seen_at_utc FROM identity_gallery "
                "WHERE last_seen_at_utc >= ? ORDER BY last_seen_at_utc, person_id",
                (since,),
            ).fetchall()
        return tuple(
            (
                row["person_id"],
                tuple(float(value) for value in json.loads(row["embedding_json"])),
                float(row["last_seen_at_utc"]),
            )
            for row in rows
        )

    def delete_older_than(self, timestamp: float) -> int:
        connection = self._database.connection()
        with self._database.lock, connection:
            cursor = connection.execute("DELETE FROM identity_gallery WHERE last_seen_at_utc < ?", (timestamp,))
        return int(cursor.rowcount)

    def delete_persons_older_than(self, timestamp: float) -> int:
        connection = self._database.connection()
        with self._database.lock, connection:
            cursor = connection.execute("DELETE FROM persons WHERE last_seen_utc < ?", (timestamp,))
        return int(cursor.rowcount)
