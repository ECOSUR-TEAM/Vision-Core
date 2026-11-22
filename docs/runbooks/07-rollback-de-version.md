# Runbook 07: Rollback de versión

**Síntoma:** una versión nueva degrada el servicio tras un deploy o un release
y hay que volver a un estado conocido.

**Regla:** nunca reviertas apuntando a `latest`. Usa un commit/tag conocido o un
digest inmutable publicado. No se mueven ni reutilizan tags.

## Verificación rápida

```bash
git log --oneline -10
git describe --tags --always
git ls-remote --tags --refs origin
docker compose --profile camera ps -a
curl http://127.0.0.1:8080/ready
```

Identifica la última versión buena y qué cambió (código, configuración o
esquema de base). Si el release tiene GitHub Release, toma los digests de
`release-digests.txt`: [releases.md](../releases.md#rollback).

## Acción

### Antes de cualquier rollback

```bash
docker compose --profile camera stop vision-core
docker run --rm -v vision-core_vision-data:/data -v "$PWD/backup:/backup" \
  alpine cp -a /data/. /backup/
docker compose --profile camera start vision-core
```

Las migraciones de SQLite son **forward-only**: volver a código anterior no
revierte el esquema. Si la versión nueva aplicó `002_metrics.sql` u otra
migración, valida con el responsable de datos antes de continuar. Procedimiento
completo en [persistence.md](../persistence.md#backup-y-restore).

### Caso A: rollback del código en este host

```bash
git fetch origin
git switch -c rollback/<version> <commit-o-tag-bueno>
docker compose --profile camera down
docker compose --profile camera up -d --build
```

Trabajar en una rama nueva evita un `HEAD` separado y permite proponer el fix
posterior. Después, vuelve a tu rama de trabajo.

### Caso B: rollback de una imagen publicada por digest

En Compose, `vision-core` y `camera-bridge` se construyen desde el código. Para
usar una imagen publicada, sustituye temporalmente `build:` por `image:` con el
digest del release:

```yaml
vision-core:
  image: ghcr.io/ecosur-team/vision-core@sha256:<runtime-digest>
```

```bash
docker compose --profile camera up -d
```

Haz lo mismo con `camera-bridge` si el cambio afectaba al puente. Conserva el
diff del archivo Compose para restaurarlo cuando se publique el fix. Los
digests y su procedimiento están en [releases.md](../releases.md#rollback).

## Señal de éxito

- `/health` y `/ready` devuelven `200`.
- El stream entra y `vision_core_frames_processed_total` crece.
- `vision_core_events_emitted_total` vuelve a aumentar al cruzar zonas.
- `/api/v1/state` no muestra nuevos `persistence.failures`.
- La versión desplegada coincide con el commit, tag o digest elegido.

## Después

1. Registra hora, versión afectada, versión restaurada y evidencia en el
   incidente; usa el registro del [índice de runbooks](README.md#registro-de-ejecución).
2. Añade la entrada correspondiente a `CHANGELOG.md` si se publica un patch.
3. No reutilices el tag malo: publica un patch nuevo con el fix. Política en
   [ADR 0006](../adr/0006-versionado-y-releases.md).
4. Si el rollback toca esquema o retención, escala al responsable de datos
   antes de reanudar la ingesta continua.
