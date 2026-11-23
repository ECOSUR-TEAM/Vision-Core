# Persistencia, retención y backup

Vision Core puede conservar eventos, historial de zonas, tracks, identidades,
sesiones y métricas en una base SQLite local. La decisión y sus límites están en
el [ADR-0002](adr/0002-persistence-and-retention.md). El código vive en
`src/vision_core/core/infrastructure/persistence/`; allí vive `event_id_for`, que
consume la serialización canónica de
`src/vision_core/core/serialization/events.py`, también usada por el monitor y
los scripts de exportación.

## Habilitación

La persistencia está desactivada por defecto. Se activa definiendo
`VISION_CORE_DB_PATH`; `VISION_CORE_DB_ENABLED=0` la desactiva explícitamente.
En Compose el valor por defecto es `/app/data/vision-core.sqlite3`, dentro del
volumen `vision-data`, por lo que sobrevive a `docker compose down`.

| Variable | Por defecto | Descripción |
|---|---|---|
| `VISION_CORE_DB_ENABLED` | `1` si hay `DB_PATH` | Activa/desactiva la persistencia |
| `VISION_CORE_DB_PATH` | `vision-core.sqlite3` | Ruta del archivo SQLite |
| `VISION_CORE_DB_FAIL_OPEN` | `1` | `1`: falla la DB y el pipeline sigue; `0`: propaga el error |
| `VISION_CORE_DB_BUSY_TIMEOUT_SECONDS` | `5` | Espera ante bloqueos |
| `VISION_CORE_EVENT_TTL_SECONDS` | `2592000` (30 días) | Retención de eventos |
| `VISION_CORE_HISTORY_TTL_SECONDS` | `604800` (7 días) | Retención de observaciones de zona |
| `VISION_CORE_IDENTITY_TTL_SECONDS` | `86400` (1 día) | Retención de embeddings y personas |
| `VISION_CORE_TRACK_TTL_SECONDS` | `86400` (1 día) | Retención de tracks |
| `VISION_CORE_SESSION_TTL_SECONDS` | `2592000` (30 días) | Retención de sesiones |
| `VISION_CORE_METRICS_TTL_SECONDS` | `2592000` (30 días) | Retención de métricas |
| `VISION_CORE_DB_PRUNE_INTERVAL_SECONDS` | `3600` | Frecuencia del worker de limpieza |

Un TTL de `0` desactiva el borrado por tiempo de ese tipo de dato. El worker
corre en un hilo `daemon` separado, nunca en la ruta de cada frame.

## Esquema y migraciones

`MigrationRunner` aplica `001_initial.sql` y `002_metrics.sql` en orden y guarda
la versión en `schema_migrations`. El mismo procedimiento crea una base vacía o
actualiza una existente sin borrar datos. No se editan migraciones ya
aplicadas: se añade una nueva.

Consultas útiles:

```bash
sqlite3 data/vision-core.sqlite3 "SELECT version, applied_at_utc FROM schema_migrations;"
sqlite3 data/vision-core.sqlite3 "SELECT COUNT(*) FROM events;"
sqlite3 data/vision-core.sqlite3 "SELECT * FROM events ORDER BY timestamp_utc DESC LIMIT 10;"
```

En Compose:

```bash
docker compose exec vision-core python -c "import sqlite3; c=sqlite3.connect('/app/data/vision-core.sqlite3'); print(c.execute('select version from schema_migrations').fetchall())"
```

La respuesta HTTP `/api/v1/state` incluye `persistence` con `enabled`, `path`,
`migrations`, `failures` y `last_error`. SQLite es local y no usa usuario,
contraseña ni URL de conexión.

## Backup y restore

Con `fail_open=1` y `WAL`, copiar solo el `.sqlite3` mientras el proceso está
activo puede perder las últimas escrituras del WAL. Procedimiento recomendado:

1. Detener el monitor: `docker compose stop vision-core`.
2. Copiar archivo, WAL y SHM:
   `cp data/vision-core.sqlite3* /backup/$(date +%F)/`.
3. Reiniciar: `docker compose start vision-core`.

Si se usa un volumen named de Docker, también se puede copiar con:

```bash
docker run --rm -v vision-core_vision-data:/data -v "$PWD/backup:/backup" \
  alpine cp -a /data/. /backup/
```

Para restaurar, detener el servicio, reemplazar los tres archivos por los del
backup con el mismo nombre y volver a arrancar. Las migraciones pendientes se
aplican solas en el próximo arranque.

## Degradación

`PersistenceService` captura errores SQLite y de sistema de archivos. Con
`fail_open=1` (por defecto) el video y el monitor siguen en memoria y
`health()` informa del fallo. Con `fail_open=0` un fallo de DB detiene el
pipeline, útil cuando la auditoría es obligatoria.

Si aparece `failures > 0` en `/api/v1/state`, revisar permisos del directorio,
espacio en disco, corrupción del archivo y bloqueos externos; no reiniciar el
proceso sin antes copiar el archivo para diagnóstico.

## Verificación

```bash
VISION_CORE_DB_PATH=/tmp/vision-core-check.sqlite3 VISION_CORE_DB_ENABLED=1 \
  python -c "from main import build_persistence; print(build_persistence().health())"
python -m pytest tests/infrastructure/persistence tests/features/pipeline tests/test_persistence_integration.py -q
python -m pytest -q -m "not slow"
ruff check . && ruff format --check . && python -m mypy
```
