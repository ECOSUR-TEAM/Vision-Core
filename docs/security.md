# Seguridad y supply chain

Este documento complementa la [política de seguridad](../SECURITY.md) con los
procedimientos operativos de dependencias, escaneo y verificación.

## Dependencias

[`.github/dependabot.yml`](../.github/dependabot.yml) revisa semanalmente los
tres ecosistemas usados por el proyecto:

| Ecosistema | Archivo | Agrupación |
|---|---|---|
| `pip` | `requirements.txt` | `minor` y `patch` en un único PR |
| `github-actions` | `.github/workflows/*.yml` | `minor` y `patch` en un único PR |
| `docker` | `Dockerfile` | `minor` y `patch` en un único PR |

Los PRs llegan con las etiquetas `dependencies` y `security`. Se revisan una vez
por semana, se ejecuta la suite completa y se fusionan solo cuando pasan los
chequeos obligatorios (tests, lint, Dependency Review y CodeQL). Los cambios
`major` llegan separados para revisar rupturas de compatibilidad.

### Versiones fijadas y reproducibilidad

`requirements.txt` fija las versiones directas con `==`, de modo que una misma
confirmación instale las mismas dependencias. `torch` y `torchvision` se instalan
desde el índice CPU de PyTorch en CI y en el `Dockerfile`; por eso se dejan sin
fijar en `requirements.txt` para no sustituir esos wheels CPU por los de CUDA de
PyPI. Cuando se cambie el índice o la versión de Python, actualiza esos dos
paquetes de forma coordinada en ambos lugares.

No se versiona un lockfile transitivo: el conjunto exacto se congela por
ejecución con `pip freeze`. Para auditar una medición o una incidencia guarda la
salida junto al reporte:

```bash
python -m pip freeze --exclude-editable > requirements.lock.txt
```

`requirements.lock.txt` es una instantánea de auditoría, no una entrada de
instalación: no se usa en CI ni en Docker. La inclusión de hashes y un lockfile
transitivo completo queda como mejora posterior; el ticket de releases	registra
SBOM y digests de las imágenes.

### Cómo actualizar dependencias y regenerar el lockfile

1. Revisa el PR semanal de Dependabot (o crea una rama con el cambio manual).
2. Edita la versión en `requirements.txt`, o el `FROM` en `Dockerfile`, o la
   referencia de la action en `.github/workflows/`.
3. Instala y comprueba el entorno:

   ```bash
   python -m pip install -r requirements.txt
   python -m pip check
   ```

4. Regenera la instantánea: `python -m pip freeze --exclude-editable > requirements.lock.txt`.
5. Verifica localmente antes de abrir el PR:

   ```bash
   python -m pytest -q
   ruff check .
   ruff format --check .
   ```

6. El PR debe pasar Dependency Review, CodeQL, CI y lint. Si una actualización
   introduce una vulnerabilidad alta/crítica con corrección disponible, reviertela
   o sube a una versión corregida. Si no hay corrección, documenta la excepción
   con justificación y fecha en
   [`.github/security-exceptions.yml`](../.github/security-exceptions.yml).

## Escaneo de código y PRs

- **Ruff** es el primer filtro (`E`, `F`, `W`, `I`) en CI y pre-commit.
- **CodeQL** analiza Python en push a `main`/`develop`, en PRs del repositorio y
  semanalmente; publica los hallazgos en **Security → Code scanning**.
- **Dependency Review** compara el grafo de dependencias del PR con la GitHub
  Advisory Database y falla en severidad `high` o superior.

## Escaneo de imágenes

El job `scan-image` de [Docker CD](../.github/workflows/docker.yml) construye
cada target (`runtime` y `camera-bridge`) sin publicarlo y ejecuta Trivy con:

- `severity: HIGH,CRITICAL`
- `ignore-unfixed: true` (no bloquea vulnerabilidades sin corrección)
- `exit-code: "1"` (falla el job si hay hallazgos corregibles)
- salida SARIF subida con `github/codeql-action/upload-sarif` y categoría
  `trivy-<target>`.

Los resultados aparecen en **Security → Code scanning** junto a los de CodeQL.
El job usa únicamente `contents: read` y `security-events: write`, y no corre en
PRs de forks para no pedir permisos de escritura con un token de solo lectura.

Para reproducir el escaneo en local:

```bash
docker build --target runtime -t vision-core-runtime:scan .
trivy image --severity HIGH,CRITICAL --ignore-unfixed vision-core-runtime:scan
```

## Activación en ajustes de GitHub

Los archivos del repositorio no pueden activar los controles que requieren
permisos de administrador. Un administrador debe revisar **Settings → Code
security and analysis** y confirmar que están activos: Dependabot alerts,
Dependabot security updates, secret scanning, push protection y code scanning.
Sin esos ajustes, los workflows siguen ejecutándose pero las alertas no aparecen
en la pestaña **Security**.

## Permisos de workflows

- `permissions: contents: read` por defecto en todos los workflows.
- `security-events: write` únicamente en los jobs que suben SARIF.
- `packages: write` únicamente en el job que publica en GHCR.
- Sin `pull_request_target`; los PRs se ejecutan con `pull_request`.
- Se recomienda fijar las actions por SHA ante un cambio de supply chain; mientras
  tanto se usan tags mayores oficiales y Dependabot vigila sus actualizaciones.

## Verificación

1. PR con una dependencia vulnerable de prueba: Dependency Review debe bloquear.
2. PR de Dependabot: debe aparecer semanalmente y agrupar `minor`/`patch`.
3. Push de un secreto falso: push protection debe rechazarlo.
4. Imagen publicada: revisar el job `scan-image` y su SARIF en GitHub Security.
5. **Security → Code scanning**: deben aparecer los hallazgos de CodeQL y Trivy.
