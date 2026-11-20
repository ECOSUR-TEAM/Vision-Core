# Política de seguridad y respuesta a vulnerabilidades

## Alcance

Esta política aplica al código, dependencias e imágenes de Vision Core
(`ECOSUR-TEAM/Vision-Core`). No cubre pentesting externo, WAF ni hardening de
infraestructura.

## Reporte de vulnerabilidades

No abras un issue público con detalles explotables. Reporta de forma privada:

1. GitHub: **Security → Advisories → New draft security advisory** en este
   repositorio (canal preferido).
2. Si no tienes acceso, escribe a los mantenedores del proyecto indicando
   componente afectado, versión, impacto y pasos de reproducción.

Confirma al reportante dentro de los **2 días hábiles**, entrega un diagnóstico
inicial dentro de los **5 días hábiles** y mantiene el reporte informado hasta el
cierre.

## Clasificación y tiempos de respuesta

| Severidad | Objetivo de mitigación |
|---|---|
| Crítica | 7 días |
| Alta | 14 días |
| Media | 30 días |
| Baja | Según disponibilidad |

La severidad se toma de GitHub Advisory Database / Trivy (CVSS y criticidad),
ajustada por contexto de explotabilidad. Las vulnerabilidades **altas y críticas
corregibles bloquean** el PR o la publicación de la imagen.

## Excepciones

No se bloquea una vulnerabilidad sin corrección disponible: Trivy usa
`ignore-unfixed: true` y Dependency Review solo evalúa el diff del grafo (no
expone `fixAvailable`). Toda excepción debe registrarse en
[`.github/security-exceptions.yml`](.github/security-exceptions.yml), validarse
contra [`.github/security-exceptions.schema.json`](.github/security-exceptions.schema.json)
y contener:

- identificador (CVE/GHSA),
- componente y versión,
- justificación (por qué no hay fix o por qué no es explotable),
- fecha de registro y fecha de revisión,
- responsable.

El archivo usa sintaxis JSON (YAML válido) para leerse con la biblioteca
estándar de Python. `scripts/security_exceptions.py` valida el esquema, genera
`.trivyignore` para Trivy y publica `allow-ghsas` para Dependency Review, de modo
que ambos scanners consumen la misma lista.

Las excepciones se revisan al menos cada mes y al actualizar dependencias.

## Controles automáticos

| Control | Dónde | Resultado |
|---|---|---|
| [Dependabot](.github/dependabot.yml) semanal y agrupado (pip, Actions, Docker) | PRs | Actualizaciones revisables |
| [Dependency Review](.github/workflows/dependency-review.yml) con `fail-on-severity: high` | PRs a `main`/`develop` | Bloquea severidad alta/crítica corregible |
| [CodeQL](.github/workflows/codeql.yml) para Python | Push, PRs del repositorio y semanal | Resultados en GitHub Security |
| Ruff (primer filtro) | CI y [pre-commit](.pre-commit-config.yaml) (`v0.3.0`) | Bloquea errores de código/imports |
| [Trivy](.github/workflows/docker.yml) y [Release](.github/workflows/release.yml) sobre la imagen construida | CD y tags `v*`, antes de publicar | SARIF en GitHub Security; falla en alta/crítica corregible |
| Secret scanning y push protection | Ajustes del repositorio (ver abajo) | Bloquea secretos antes del push |

Todos los workflows usan `permissions` explícitos y `contents: read` por defecto;
`security-events: write` solo se otorga a los jobs que publican SARIF,
`packages: write` solo al job que publica imágenes, `pull-requests: write` solo a
Dependency Review y `contents: write` solo al job que crea releases. No se usa
`pull_request_target`.

## Secret scanning y push protection

Estos controles se configuran en el sitio web de GitHub y requieren permisos de
administrador (no se pueden activar desde un archivo del repositorio):

1. En **Settings → Code security and analysis** activa **Dependency graph**,
   **Dependabot alerts**, **Dependabot security updates**, **Secret scanning** y
   **Push protection**.
2. Opcionalmente activa **Secret scanning for custom patterns** para patrones
   propios del proyecto.
3. Verificación: al intentar hacer push de un secreto falso (por ejemplo un token
   de prueba con formato válido), GitHub debe rechazar el push. Si el repositorio
   es un fork o la rama está protegida, comprueba el estado en la pestaña
   **Security → Secret scanning**.

Sin Dependency Graph, el job de Dependency Review falla y bloquea el PR; no se
omite ni se degrada a advisory. Marca ese check como requerido en branch
protection después de habilitar el grafo.

Los hallazgos de los workflows se publican automáticamente en **Security → Code
scanning** cuando el repositorio tiene habilitada esa pestaña; si no aparece,
un administrador debe activarla en la misma sección de ajustes.

No almacenes secretos en `.env`, imágenes ni logs. `.env` está excluido por
`.gitignore` y `.dockerignore`; usa `.env.example` como plantilla.

## Actualizaciones y referencias

- [Guía de supply chain y actualización de dependencias](docs/security.md).
- [Excepciones y su esquema](.github/security-exceptions.yml).
- Coordinación de SBOM/digests con el ticket de releases y revisión de licencias
  en su ticket correspondiente.
