# Runbook 04: Disco lleno y retención

**Síntoma:** `/ready` devuelve `503` por disco, SQLite crece sin control o
`/api/v1/state` muestra `persistence.failures > 0`.

## Verificación rápida

```bash
curl http://127.0.0.1:8080/ready
curl http://127.0.0.1:8080/api/v1/state
docker compose --profile camera exec vision-core df -h /model-cache /app/data
docker compose --profile camera logs --tail 80 vision-core
```

- `VISION_CORE_MINIMUM_FREE_DISK_MB` (por defecto `500`) define el umbral de
  readiness; `VISION_CORE_DISK_CHECK_PATH` es `/model-cache` en Compose.
- En `/api/v1/state`, el bloque `persistence` informa de `enabled`, `path`,
  `migrations`, `failures` y `last_error`. Con `VISION_CORE_DB_FAIL_OPEN=1` el
  video sigue en memoria aunque la base falle; con `0` el pipeline se detiene.
- Consultas de ejemplo en [persistence.md](../persistence.md#esquema-y-migraciones).

## Acción

1. **Confirmar la causa real:** revisa el espacio del volumen de datos, de la
   caché de modelos y del host. No asumas que SQLite es el único consumo.
2. **Retención:** revisa los TTL en `.env`. Valores por defecto: eventos 30
   días, observaciones 7 días, identidades y tracks 1 día, sesiones y métricas
   30 días. El worker (`VISION_CORE_DB_PRUNE_INTERVAL_SECONDS=3600`) corre en
   segundo plano; `0` en un TTL desactiva el borrado de ese tipo.
3. **Ajustar y recrear:** edita los TTL o el intervalo en `.env` y recrea el
   servicio:

   ```bash
   docker compose --profile camera up -d
   ```

   No borres filas a mano sin antes copiar la base.
4. **Liberar espacio:** elimina artifacts temporales y videos de prueba
   antiguos; limpia imágenes Docker no usadas si aplica. No borres
   `/model-cache` salvo que puedas volver a descargar los pesos.
5. **Copiar antes de tocar la base:** con `fail_open=1` y WAL, copiar solo el
   `.sqlite3` en caliente puede perder escrituras. Procedimiento seguro:

   ```bash
   docker compose --profile camera stop vision-core
   docker run --rm -v vision-core_vision-data:/data -v "$PWD/backup:/backup" \
     alpine cp -a /data/. /backup/
   docker compose --profile camera start vision-core
   ```

   El detalle (incluido WAL/SHM y restore) está en
   [persistence.md](../persistence.md#backup-y-restore).
6. **Si hay `failures > 0`:** revisa permisos del directorio, espacio y
   bloqueos externos antes de reiniciar. Conserva una copia del archivo para
   diagnóstico.

## Señal de éxito

- `/ready` vuelve a `200`.
- `/api/v1/state` muestra `persistence.failures = 0` y el tamaño de la base
  deja de crecer o se reduce tras la purga.
- El monitor y el stream siguen activos durante la limpieza (fail-open).

## Escalado

Si la base está corrupta o el disco se llena de nuevo en menos de un turno,
documenta el consumo por tipo de dato y escala al responsable de retención.
La política de privacidad y borrado de video se coordina con el ticket 42;
este runbook no elimina frames ni video. Contexto:
[ADR 0002](../adr/0002-persistence-and-retention.md).
