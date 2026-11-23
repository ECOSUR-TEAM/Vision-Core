# ADR 0002: Persistencia y retención de eventos, tracks e historial

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-19 |
| Tipo | Arquitectura / Datos |
| Prioridad | Alta |
| Ticket | ECM-79 |
| Etiquetas | `persistence`, `retention`, `database`, `repositories`, `ttl`, `adr` |
| Dependencias | Tickets 29 y 31; sprint 4 (tickets 20 y 21) |
| Impacto | Base para auditoría, replay y futura multi-cámara |

## Contexto

Los eventos de puerta, el historial de zonas, las identidades de ReID y las
métricas viven hoy en estructuras en memoria (`deque`, `dict`, `set`). Al
reiniciar el proceso se pierde todo: no hay auditoría, no se puede consultar el
histórico ni reconstruir una sesión. El `compose` actual tampoco monta un volumen
de datos, por lo que cualquier solución debe definir dónde vive el archivo.

El despliegue objetivo es **un único nodo con una cámara**, con posibilidad de
crecer a varias cámaras en el mismo host. No hay multi-tenant ni sincronización
entre nodos (fuera de alcance). El dominio no debe conocer SQL ni una librería
concreta.

## Decisión

### Motor

Adoptar **SQLite** como primer motor, con `sqlite3` de la biblioteca estándar:

- Un solo nodo, una o varias cámaras en el mismo host: una única base de datos
  local con `session_id` y `camera_id` para distinguir orígenes.
- Sin servidor, sin credenciales de red y sin dependencias nuevas; apto para el
  volumen esperado (ver tamaño estimado).
- `WAL` + `busy_timeout` para lecturas concurrentes del monitor y escrituras del
  pipeline.

**Límite documentado:** SQLite no es adecuado para escritura concurrente desde
varios hosts, ni para replicación. Si aparece un segundo nodo, se migrará a
**PostgreSQL** manteniendo los mismos repository ports y cambiando solo el
adaptador; la URL y las credenciales se leerán de variables de entorno
específicas cuando se implemente (nunca del código ni de logs). El tercer destino
evaluado, archivos JSONL, queda como formato de exportación/backup, no como
almacén de consulta.

### Qué se persiste

| Dato | Tabla | Contenido | TTL por defecto |
|---|---|---|---|
| Eventos | `events` | `event_id`, tipo, `person_id`, `session_id`, timestamp UTC, metadata JSON | 30 días |
| Historial de zonas | `zone_observations` | persona, zona, posición, timestamp, `event_id` | 7 días |
| Tracks | `tracks` | `session_id`, `track_id` local, `person_id`, bbox, timestamp | 1 día |
| Embeddings | `identity_gallery` | `person_id`, embedding normalizado, `last_seen_at` | 1 día |
| Personas | `persons` | primera/última vez vista, metadata | 1 día (inactividad) |
| Zonas | `zones` | nombre y polígono configurado | sin expiración |
| Sesiones | `sessions` | inicio, fin, cámara | 30 días |
| Métricas | `metrics` | nombre, valor, timestamp, `session_id` | 30 días |

`event_id` es la clave de idempotencia: `UNIQUE(event_id)` + `INSERT OR IGNORE`.
El productor puede enviar el mismo `event_id` al reintentar; si no lo envía, el
adaptador deriva un identificador determinista del evento inmutable. Un evento
emitido dos veces se cuenta una sola vez.

Todos los timestamps se guardan como epoch UTC en columnas `*_utc` y las
marcas de auditoría como ISO-8601 con sufijo `Z`.

### Qué no se persiste

- **Frames, crops ni video**: son datos opacos, de gran volumen y con política
  de retención propia (ticket 42). Solo se guarda la posición y el bbox.
- **El estado transitorio del monitor** (`jpeg`, FPS, `deque` de 100 eventos):
  se recalcula o se reconstruye desde la DB.
- **IDs locales de track como identidad**: `track_id` se reutiliza; la identidad
  persistente es `person_id`.
- **Secretos, URLs RTSP ni credenciales**: nunca entran en la DB ni en logs.

### Contratos y capas

Los repository ports viven en `vision_core.core.contracts` porque los
datos persistidos cruzan varios slices (puerta, ReID, monitor) y son parte del
kernel compartido. Cada puerto es una `ABC` sin SQL, sin
`sqlite3` y sin tipos de infraestructura.

Las implementaciones `Sqlite*` viven en
`vision_core.core.infrastructure.persistence`. El dominio y los features no importan
este paquete: la inyección se hace en `main.py`. Se respeta una clase por
archivo. La serialización canónica de eventos vive en
`vision_core.core.serialization.events`; `event_id_for`, el monitor y los scripts
consumen el payload versionado para calcular `event_id`, construir snapshots y
exportar JSONL con idéntico contenido.

### Esquema y migraciones

Los archivos `migrations/001_initial.sql` y `002_metrics.sql` se aplican en orden
por `MigrationRunner`, que registra la versión en `schema_migrations`. La misma
ruta sirve para crear una DB vacía y para actualizar una existente; los datos ya
guardados se conservan. Índices: `events(event_id)` único, `events(timestamp_utc)`,
`events(person_id, timestamp_utc)`, `zone_observations(person_id, timestamp_utc)`,
`tracks(session_id, timestamp_utc)`, `identity_gallery(last_seen_at_utc)` y
`metrics(timestamp_utc)`.

### Retención y degradación

`RetentionJob.run_once()` aplica un TTL distinto por tipo de dato y
`RetentionWorker` lo ejecuta en segundo plano cada
`VISION_CORE_DB_PRUNE_INTERVAL_SECONDS`. Un TTL de `0` significa "sin borrado
por tiempo". La limpieza nunca corre en la ruta crítica de cada frame.

`PersistenceService` es fail-open por defecto (`VISION_CORE_DB_FAIL_OPEN=1`):
si la DB no existe, está bloqueada o corrupta, captura el error, expone
`health()` con el tipo de error y el número de fallos, y el pipeline de video y
el monitor siguen funcionando en memoria. Con `fail_open=0` el error se propaga
para despliegues que exigen persistencia obligatoria. El estado se publica en
`/api/state` como `persistence` sin mensajes nativos ni rutas.

### Tamaño esperado

Un evento ocupa ~0.5 KB (metadata pequeña). Con 1 cámara, ~50 eventos/día y 10
personas activas: ~25 MB/año de eventos, ~50 MB/año de observaciones y
~5 MB/año de embeddings (128 floats por persona). Con 30 días de retención la
DB se mantiene por debajo de ~20 MB. Las estimaciones se revisan al cambiar la
frecuencia de eventos o el tamaño del embedding.

## Consecuencias

### Positivas

- Reiniciar el proceso no pierde el historial: los repositorios lo leen de la DB.
- Idempotencia comprobable y auditoría con timestamps UTC.
- Retención configurable por tipo de dato y backup de un único archivo.
- Cambiar a PostgreSQL no requiere tocar el dominio.

### Negativas y costes

- Nueva tabla de migraciones y un worker de limpieza que mantener.
- Escritura síncrona desde el hilo del pipeline (acotada por el guard de
  degradación).
- La recuperación de ReID depende de que el embedder sea estable entre
  reinicios; hoy se persiste la galería, no el modelo.

### Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| DB bloqueada por el monitor | `WAL`, `busy_timeout` y conexión protegida por `RLock` |
| Pérdida por disco lleno | `health()` degradea y el pipeline continúa; monitor warning |
| Migración incompatible | Migraciones versionadas y `schema_migrations`; no se editan las ya aplicadas |
| Duplicados por reintento | `UNIQUE(event_id)` + `INSERT OR IGNORE` |
| Crecimiento sin control | TTL por tipo y worker periódico |

## Alternativas consideradas

1. **PostgreSQL desde el inicio.** Descartada: redundant para un nodo, exige
   servidor, credenciales y operación adicional.
2. **Solo archivos JSONL.** Descartada: simple para append, deficiente para
   consultas, índices y retención selectiva; se mantiene como exportación.
3. **Persistir frames/video.** Descartada: coste desproporcionado y política de
   retención ajena a este ticket.
4. **Repositorios en cada feature.** Descartada: los datos son transversales y
   pertenecen al kernel compartido.

## Verificación

```bash
python -m pytest tests/infrastructure/persistence tests/features/pipeline tests/test_persistence_integration.py -q
python -m pytest tests/architecture -q
python -m pytest -q -m "not slow"
ruff check . && ruff format --check .
python -m mypy
python -m compileall -q src tests main.py
! grep -R "vision_core.features" src/vision_core/core/infrastructure
grep -R "event_to_json" src tests
```

Los tests cubren migración desde cero y upgrade, idempotencia de `event_id`,
purga por TTL, reapertura tras "reinicio" del proceso y degradación sin DB.
El procedimiento operativo está en [persistencia y backup](../persistence.md).
