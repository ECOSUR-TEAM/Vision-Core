# ADR 0006: Versionado semántico, releases y rollback

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-20 |
| Tipo | Operación / Proceso |
| Prioridad | Media |
| Ticket | ECM-84 (documenta la decisión de ECM-82) |
| Etiquetas | `adr`, `release`, `semver`, `changelog`, `rollback` |
| Dependencias | ADR 0001; CI/CD de ECM-70 y ECM-71; ADR 0002 para esquema de DB |
| Impacto | Publicación de imágenes, changelog y recuperación de incidentes |

## Contexto

Publicar `latest` sin versión ni registro de cambios impide saber qué está en
producción ni volver a un estado conocido. Hacía falta un contrato entre
desarrollo y operación: qué commit se publica, cómo se nombra, dónde se
documenta y cómo se revierte.

## Decisión

- **SemVer** con tags inmutables `vMAJOR.MINOR.PATCH` (con prerelease
  opcional). La versión de `pyproject.toml` debe coincidir con el tag base;
  `.github/workflows/release.yml` lo valida junto con la ascendencia del commit
  y la existencia de la sección en `CHANGELOG.md`.
- El workflow de release es el único publicador para tags `v*`. Publica
  `X.Y.Z` y `latest` para releases estables, ejecuta tests, lint y Trivy sobre
  `vision-core` y `camera-bridge`, y adjunta los digests al GitHub Release.
  Docker CD publica solo `main` y `sha-<7>`; son referencias móviles, no
  releases.
- `CHANGELOG.md` sigue Keep a Changelog: los cambios se escriben en
  `Unreleased` mientras se desarrollan y se congelan al crear el tag. No se
  reescribe una sección publicada.
- Los hotfixes parten de `main` como `hotfix/vX.Y.Z`, se merger por PR y se
  etiquetan con un nuevo patch; nunca se mueve ni se reutiliza un tag.
- El rollback se hace con la **versión anterior conocida**: código (checkout
  del commit/tag bueno y rebuild) o imagen publicada por **digest inmutable**
  (`@sha256:...`). Nunca se revierte apuntando a `latest`.
- Las migraciones de SQLite son forward-only. Un rollback de código no revierte
  el esquema: antes de volver se comprueba la compatibilidad y se conserva un
  backup de la base (ver [runbook de rollback](../runbooks/07-rollback-de-version.md)).

## Consecuencias

### Positivas

- Cada despliegue se puede identificar y reproducir por tag o digest.
- El changelog explica el "qué y por qué" sin leer diffs.
- El rollback tiene un procedimiento ensayado antes del incidente.

### Negativas y costes

- Publicar exige actualizar versión, changelog, CI verde y aprobación.
- Los digests deben conservarse con al menos los últimos 10 releases.

### Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Tag creado antes de tiempo | Dry run: `gh workflow run release.yml -f tag=vX.Y.Z -f dry_run=true`. |
| Rollback incompatible con la DB | Backup antes de liberar y validación de migraciones en el runbook. |
| Argumentar que "latest es estable" | `docs/releases.md` y este ADR definen `latest` como móvil. |

## Alternativas consideradas

1. **Desplegar siempre `latest`.** Descartada: no reproducible.
2. **Tags móviles por rama como único mecanismo.** Descartada: `main` y
   `sha-<7>` son para CD continuo, no para releases.
3. **Reescribir tags cuando hay un error.** Descartada: rompe cachés y deja
   clientes con una versión que ya no existe. Publicar un patch nuevo.

## Verificación

```bash
git ls-remote --tags --refs origin
gh workflow run release.yml -f tag=vX.Y.Z -f dry_run=true
python -m pytest -q
ruff check .
```

Nota: al escribir este ADR no había tags publicados en el remoto; el primer
release debe crear el tag base que corresponda a la versión declarada. El
proceso operativo está en [releases](../releases.md).

## Enmiendas

| Fecha | Cambio | Motivo | ADR que la motiva |
|---|---|---|---|
| - | - | - | - |
