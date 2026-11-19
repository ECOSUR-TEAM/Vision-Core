# Seguridad y supply chain

Este documento complementa la [política de seguridad](../SECURITY.md) con los
procedimientos operativos de dependencias, escaneo y verificación.

## Dependencias

[`.github/dependabot.yml`](../.github/dependabot.yml) revisa semanalmente los
tres ecosistemas usados por el proyecto:

| Ecosistema | Archivo | Agrupación |
|---|---|---|
| `pip` | `requirements*.txt` | `minor` y `patch` en un único PR |
| `github-actions` | `.github/workflows/*.yml` | `minor` y `patch` en un único PR |
| `docker` | `Dockerfile` | `minor` y `patch` en un único PR |

Los PRs llegan con la etiqueta `dependencies`; la etiqueta `security` se reserva
para actualizaciones de seguridad confirmadas y se aplica durante la triaje, no
de forma automática a todas las PRs de Dependabot. Se revisan una vez por semana,
se ejecuta la suite completa y se fusionan solo cuando pasan los chequeos
obligatorios (tests, lint, Dependency Review y CodeQL). Los cambios `major`
llegan separados para revisar rupturas de compatibilidad.

### Versiones fijadas y reproducibilidad

`requirements.txt` fija las versiones directas con `==`, de modo que una misma
confirmación instale las mismas dependencias. `torch` y `torchvision` viven en
[`requirements-cpu.txt`](../requirements-cpu.txt), que declara
`--index-url https://download.pytorch.org/whl/cpu`: instalar ese archivo antes
que `requirements.txt` evita sustituir los wheels CPU por los de CUDA de PyPI.
`pytest` está en [`requirements-dev.txt`](../requirements-dev.txt), que no se
instala en la imagen. Cuando se cambie el índice o la versión de Python,
actualiza esos dos paquetes de forma coordinada en CI y en el `Dockerfile`.

No se versiona un lockfile transitivo: el conjunto exacto se congela por
ejecución con `pip freeze`. Para auditar una medición o una incidencia guarda la
salida junto al reporte:

```bash
python -m pip freeze --exclude-editable > requirements.lock.txt
```

`requirements.lock.txt` es una instantánea de auditoría, no una entrada de
instalación: no se usa en CI ni en Docker y está excluido por
[`.gitignore`](../.gitignore). La inclusión de hashes y un lockfile transitivo
completo queda como mejora posterior; el ticket de releases	registra SBOM y
digests de las imágenes.

### Cómo actualizar dependencias y regenerar el lockfile

1. Revisa el PR semanal de Dependabot (o crea una rama con el cambio manual).
2. Edita la versión en `requirements*.txt`, o el `FROM` en `Dockerfile`, o la
   referencia de la action en `.github/workflows/`.
3. Instala y comprueba el entorno:

   ```bash
   python -m pip install -r requirements-cpu.txt
   python -m pip install -r requirements-dev.txt
   python -m pip check
   ```

4. Regenera la instantánea: `python -m pip freeze --exclude-editable > requirements.lock.txt`.
5. Verifica localmente antes de abrir el PR:

   ```bash
   python -m pytest -q
   ruff check .
   ruff format --check .
   ```

6. El PR debe pasar Dependency Review (cuando esté habilitado), CodeQL, CI y
   lint. Si una actualización introduce una vulnerabilidad alta/crítica con
   corrección disponible, reviertela o sube a una versión corregida. Si no hay
   corrección, documenta la excepción con justificación y fecha en
   [`.github/security-exceptions.yml`](../.github/security-exceptions.yml),
   validada contra
   [su esquema](../.github/security-exceptions.schema.json).

`python scripts/security_exceptions.py` valida ese archivo, genera
`.trivyignore` para Trivy y publica `allow-ghsas` para Dependency Review. Así una
misma excepción se aplica en ambos scanners sin editar dos listas distintas.

## Escaneo de código y PRs

- **Ruff** es el primer filtro (`E`, `F`, `W`, `I`) en CI y en el hook configurado
  en [`.pre-commit-config.yaml`](../.pre-commit-config.yaml) (`v0.3.0`, la misma
  versión que el workflow de lint).
- **CodeQL** analiza Python en push a `main`/`develop`, en PRs del repositorio y
  semanalmente; publica los hallazgos en **Security → Code scanning**. Los PRs
  de forks se omiten porque su token no puede publicar SARIF; la protección de
  rama debe tenerlo en cuenta.
- **Dependency Review** compara el grafo de dependencias del PR con la GitHub
  Advisory Database y falla en severidad `high` o superior, siempre que el
  administrador haya activado el grafo y la variable
  `DEPENDENCY_GRAPH_ENABLED=true`; si no, el job se omite.

## Escaneo de imágenes

El job `scan-image` de [Docker CD](../.github/workflows/docker.yml) construye
cada target (`runtime` y `camera-bridge`) sin publicarlo y ejecuta Trivy con:

- `severity: HIGH,CRITICAL`
- `ignore-unfixed: true` (no bloquea vulnerabilidades sin corrección)
- `exit-code: "1"` (falla el job si hay hallazgos corregibles)
- `trivyignores: .trivyignore`, generado desde
  [`.github/security-exceptions.yml`](../.github/security-exceptions.yml)
- salida SARIF subida con `github/codeql-action/upload-sarif` y categoría
  `trivy-<target>`.

El job `publish` tiene `needs: scan-image`, por lo que la imagen no se publica en
GHCR si Trivy falla en cualquiera de los dos targets.

Los resultados aparecen en **Security → Code scanning** junto a los de CodeQL.
El job usa únicamente `contents: read` y `security-events: write`, y no corre en
PRs de forks para no pedir permisos de escritura con un token de solo lectura.
En PRs del mismo repositorio sí corre y actúa como gate antes del merge;
`packages: write` solo se otorga al job `publish`.

Para reproducir el escaneo en local:

```bash
python scripts/security_exceptions.py --trivy-ignore .trivyignore
docker build --target runtime -t vision-core-runtime:scan .
trivy image --severity HIGH,CRITICAL --ignore-unfixed --ignorefile .trivyignore \
  vision-core-runtime:scan
```

## Activación en ajustes de GitHub

Los archivos del repositorio no pueden activar los controles que requieren
permisos de administrador. Un administrador debe revisar **Settings → Code
security and analysis** y confirmar que están activos: **Dependency graph**,
Dependabot alerts, Dependabot security updates, secret scanning, push protection
y code scanning. Además debe crear la variable `DEPENDENCY_GRAPH_ENABLED=true`
en **Settings → Secrets and variables → Actions → Variables**.

Sin el grafo o sin la variable, `actions/dependency-review-action` falla con
`Dependency review is not supported on this repository. Please ensure that
Dependency graph is enabled`; por eso el workflow omite el job hasta que ambos
estén configurados. Marca el check como requerido solo después de habilitarlo.
Sin los ajustes de **Code security and analysis**, las alertas no aparecen en la
pestaña **Security**.

## Permisos de workflows

- `permissions: contents: read` por defecto en todos los workflows.
- `security-events: write` únicamente en los jobs que suben SARIF.
- `packages: write` únicamente en el job que publica en GHCR.
- Sin `pull_request_target`; los PRs se ejecutan con `pull_request`.
- Se recomienda fijar las actions por SHA ante un cambio de supply chain; mientras
  tanto se usan tags mayores oficiales y Dependabot vigila sus actualizaciones.

## Verificación

1. PR con una dependencia vulnerable de prueba: Dependency Review debe bloquear
   (con el grafo y la variable activos).
2. PR de Dependabot: debe aparecer semanalmente con la etiqueta `dependencies`.
3. Push de un secreto falso: push protection debe rechazarlo.
4. Push a `main`: `publish` no debe iniciarse hasta que `scan-image` termine sin
   hallazgos `HIGH`/`CRITICAL` corregibles; revisa su SARIF en GitHub Security.
5. **Security → Code scanning**: deben aparecer los hallazgos de CodeQL y Trivy.
