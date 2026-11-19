# Seguridad y supply chain

Este documento describe los controles obligatorios del repositorio y la
política de bloqueo para Dependabot, Dependency Review y el escaneo de imágenes.

## Dependencias

Las versiones directas se fijan en `requirements.txt`. Un administrador debe
habilitar **Dependency graph** y **Dependabot alerts** en
*Settings → Code security and analysis*; los archivos del repositorio no pueden
activar esos ajustes por sí solos.

## Dependency Review

[`.github/workflows/dependency-review.yml`](../.github/workflows/dependency-review.yml)
se ejecuta en cada PR a `main` o `develop` con `fail-on-severity: high`. El job
no usa `continue-on-error`: una vulnerabilidad alta o crítica con corrección
disponible bloquea el PR. El resumen se publica como comentario mediante
`comment-summary-in-pr: always`, por lo que el job solicita únicamente
`pull-requests: write` además de `contents: read`.

Si Dependency Graph está deshabilitado, la action falla y el PR no se puede
fusionar hasta que un administrador active el grafo. No se sustituye el reporte
por una aprobación automática ni se degrada a advisory.

## Escaneo de imágenes

El workflow [Release](../.github/workflows/release.yml) construye cada imagen,
ejecuta Trivy con `severity: HIGH,CRITICAL`, `ignore-unfixed: true` y
`exit-code: "1"`, y solo publica en GHCR si el escaneo termina sin hallazgos
corregibles. El SARIF se sube a *Security → Code scanning*. El job de publicación
solicita `packages: write` y `security-events: write`; el job que crea el GitHub
Release solicita `contents: write` y no participa en tests ni builds.

El workflow [Docker CD](.github/workflows/docker.yml) publica `main` y el SHA
corto, sin tags semánticos ni `latest`; las versiones se publican únicamente
desde el workflow de Release.

## Permisos

- `contents: read` por defecto.
- `pull-requests: write` solo en Dependency Review, para el comentario resumen.
- `security-events: write` solo en los jobs que suben SARIF.
- `packages: write` solo en el job que publica imágenes.
- `contents: write` solo en el job que crea el GitHub Release.
