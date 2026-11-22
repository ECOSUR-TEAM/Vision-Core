from pathlib import Path

from vision_core.core.infrastructure.persistence.utc import utc_text


class MigrationRunner:
    def __init__(self, connection, *, directory: Path | None = None):
        self._connection = connection
        self._directory = directory or Path(__file__).with_name("migrations")

    def migrate(self, target: str | None = None) -> tuple[str, ...]:
        scripts = sorted(self._directory.glob("*.sql"))
        names = [script.stem for script in scripts]
        if target is not None and target not in names:
            raise ValueError(f"Migración desconocida: {target}")
        with self._connection:
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at_utc TEXT NOT NULL)"
            )
            applied = {row[0] for row in self._connection.execute("SELECT version FROM schema_migrations")}
            newly_applied: list[str] = []
            for script, name in zip(scripts, names):
                if name in applied:
                    continue
                if target is not None and name > target:
                    break
                self._connection.executescript(script.read_text(encoding="utf-8"))
                self._connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at_utc) VALUES (?, ?)",
                    (name, utc_text()),
                )
                newly_applied.append(name)
        return tuple(newly_applied)
