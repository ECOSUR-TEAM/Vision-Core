# Contributing a Vision Core

Esta es la fuente única del flujo de trabajo del equipo. Aplica a `main`,
`develop` y a toda rama de ticket `ECM-*`. La configuración de owners está en
[`.github/CODEOWNERS`](.github/CODEOWNERS); los chequeos automáticos están en
[`.github/workflows/`](.github/workflows/).

## 1. Preparación

```bash
git fetch origin
git switch develop
git pull --ff-only origin develop
make setup
make test
make lint
```

Si algo falla antes de crear la rama, corrígelo en `develop` o reporta el
problema; no arrastres fallos conocidos a un PR nuevo. Consulta
[desarrollo local](docs/development.md) y [pruebas](docs/testing.md) para el
entorno completo.

## 2. Convención de branches

- Base: siempre `develop`, actualizada desde `origin/develop`.
- Formato: `ECM-<numero>-slug-en-minusculas-y-guiones`.
- Ejemplo: `ECM-85-estandarizar-proceso-de-pr-codeowners-y-definition-of-done`.

```bash
git switch -c ECM-85-mi-cambio
```

Excepciones documentadas en [releases](docs/releases.md):
`release/vX.Y.Z` y `hotfix/vX.Y.Z` (este último sale de `main` y se hace
backport a `develop`). No se crean branches personales ni `feature/*` para
trabajo con ticket Jira.

## 3. Convención de commits

Formato: `<type>(<scope>): <descripción en imperativo>`

- `scope` opcional: `video`, `detection`, `reid`, `door`, `monitor`, `pipeline`,
  `infra`, `ci`, `docs`, `tests`.
- Tipos permitidos: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `style`,
  `build`, `ci`, `chore`, `deps`, `revert`.
- Cambios incompatibles: `feat(api)!: ...` o footer
  `BREAKING CHANGE: descripción`.
- Un commit, un propósito. Sin `WIP` en el mensaje final: usa PR en borrador.
- Minúsculas, sin punto final y con el número de ticket en el cuerpo si ayuda
  a la trazabilidad.

Ejemplos:

```text
feat(monitor): add ready endpoint and rolling health state
fix(door): reject polygons with fewer than three points
ci: require type check on pull requests
docs(adr): record multi-camera execution model
deps: bump ruff to 0.3.0
```

## 4. Flujo de pull request

1. Trabaja en commits atómicos y ejecuta la verificación local (sección 7).
2. Sube la rama y abre el PR contra `develop` (o `main` solo para releases/hotfix).
3. Usa obligatoriamente la
   [plantilla de PR](.github/PULL_REQUEST_TEMPLATE.md). No borres secciones:
   escribe `N/A` cuando algo no aplique.
4. Enlaza el ticket de Jira y explica cómo probar, qué evidencia se generó, los
   riesgos y el rollback.
5. La plantilla debe estar completa antes de solicitar revisión. Los PRs sin
   plantilla se devuelven sin revisión de código.
6. Resuelve los comentarios y vuelve a pedir aprobación si haces cambios
   sustanciales después de una aprobación.

Tamaño recomendado: hasta ~400 líneas modificadas y ~10 archivos. Si el cambio
es mayor, divídelo por feature/slice, por capa (`domain` → `application` →
`infrastructure`), separando refactor de comportamiento, o apilando PRs
pequeños. Los PRs grandes deben justificar por qué no se pueden dividir.

## 5. Owners y aprobaciones

Los owners se solicitan automáticamente según
[`.github/CODEOWNERS`](.github/CODEOWNERS).

| Área | Rutas principales | Owners |
|---|---|---|
| Video | `features/video/`, `infrastructure/video/`, `tests/features/video/` | @bchanona, @Ameth-Toledo |
| Detection | `features/detection/`, `infrastructure/detection/`, `tests/features/detection/` | @Carlosss2, @Ameth-Toledo |
| ReID | `features/reid/`, `infrastructure/reid/`, `tests/features/reid/` | @bchanona |
| Door / zonas | `features/door/`, `infrastructure/door/`, `config/zones*` | @MelissaZarate08 |
| Monitor / HTTP / UI | `features/monitor/`, `infrastructure/monitor/`, `tests/e2e/test_monitor_e2e.py` | @bchanona; UI/index.html también @Carlosss2 |
| Pipeline / orquestación | `features/pipeline/`, `main.py`, `tests/integration/` | @FabricioPRZ; composition root también @Ameth-Toledo |
| Infra / CI / seguridad | `.github/`, `Dockerfile`, `docker-compose*.yml`, `Makefile`, `pyproject.toml`, `scripts/`, `SECURITY.md` | @bchanona, @Carlosss2 |
| Transversal | `shared/`, `domain/`, `settings/`, `persistence/`, `docs/`, regla `*` | @Ameth-Toledo, @bchanona, @Carlosss2 |

Se considera **transversal** cualquier cambio que toque dos o más features,
contratos DTO compartidos, `shared/`, `domain/`, `settings/`, `main.py`, CI o
esquemas de configuración. En ese caso se requieren:

- aprobación de un owner transversal; y
- aprobación del owner de cada feature afectada.

Para seguridad, dependencias o releases se requiere además un security reviewer:
@bchanona o @Carlosss2, según [SECURITY.md](SECURITY.md) y
[docs/releases.md](docs/releases.md).

Pueden aprobar los owners indicados y cualquier mantenedor con acceso de
escritura en rutas sin owner específico, pero eso **no sustituye** a los owners
cuando CODEOWNERS aplica. No pueden aprobar: el autor del PR, bots
(`dependabot[bot]`, `Copilot`), cuentas sin acceso de escritura ni aprobaciones
automáticas o impersonales.

## 6. SLA de revisión y escalamiento

| Situación | Primera respuesta | Objetivo de merge/rechazo |
|---|---|---|
| PR normal | 1 día hábil | 2 días hábiles |
| PR pequeño (≤ 400 líneas) | 1 día hábil | 1 día hábil |
| Seguridad, incidencia o hotfix | 4 horas hábiles | El mismo día hábil |

Escalamiento:

1. Vencido el SLA, menciona al owner en el PR y deja comentario con la fecha.
2. Un día hábil después sin respuesta, escala a los owners transversales del
   área.
3. Para seguridad o hotfix, escala de inmediato a @bchanona y @Carlosss2.
4. Si el autor no responde a los comentarios en 2 días hábiles, marca el PR como
   borrador o ciérralo y reabrilo cuando esté listo.

El SLA se mide en días hábiles y se registra en el PR: el cumplimiento es
responsabilidad de reviewers y autores.

## 7. Definition of Done

Un ticket solo se marca como terminado cuando el PR cumple todo lo siguiente.
Si algo no aplica, indícalo explícitamente en la plantilla.

| Criterio | Evidencia mínima |
|---|---|
| Tests actualizados y verdes | Pruebas nuevas o ajustadas + check `Unit + Integration` en verde |
| Cobertura | Umbral global 80% y umbrales por módulo (`check_coverage`) |
| Lint, formato y tipos | `make lint`, `make format-check`, `python -m mypy` y `compileall` sin errores |
| Arquitectura | Una clase por archivo, reglas de imports y convención DTO respetadas |
| Documentación / ADR | README o `docs/` actualizados; ADR nuevo si cambia una decisión |
| Observabilidad | Logs estructurados, métricas o health actualizados si el comportamiento cambia |
| Seguridad / privacidad | Sin secretos en logs, sin video personal en artifacts, permisos y dependencias revisados |
| Rollback | Pasos concretos o `N/A` justificado en el PR |

Comandos locales equivalentes a CI:

```bash
make test
make lint
make format-check
python -m mypy
python -m compileall -q src tests main.py
python -m pytest -q -m "not slow" \
  --cov=vision_core --cov-branch \
  --cov-report=term-missing \
  --cov-report=json:coverage.json \
  --cov-fail-under=80
python -m vision_core.scripts.check_coverage coverage.json
```

Para cambios en monitor/HTTP también ejecuta `python -m pytest -q -m slow` y
adjunta el resultado. Ese job es nightly y no bloquea el PR.

## 8. Chequeos y rulesets

Los rulesets se configuran en la UI de GitHub y no están versionados en este
repositorio. Deben exigir para `develop` y `main`:

- PR con al menos 1 aprobación; 2 para cambios transversales.
- Revisión de Code Owners y resolución de conversaciones.
- Branch actualizada con la base antes de fusionar.
- Checks requeridos: `Unit + Integration`, `Build`, `Lint`, `Type Check`,
  `Lint and Format / lint` y `Dependency Review`.
- `CodeQL` y `Escanear imagen con Trivy` cuando el workflow corra. Ambos omiten
  PRs de forks, por lo que no deben marcarse como requeridos para forks.
- No merge directo; los administradores también respetan el ruleset.

Si un check falla, no se omite: corrige el cambio o documenta la excepción de
seguridad en `.github/security-exceptions.yml` con su owner y fecha de revisión.

## 9. Plantillas de issues

Usa la plantilla que corresponda; todas incluyen criterios de aceptación:

- [Bug](.github/ISSUE_TEMPLATE/bug_report.md)
- [Feature](.github/ISSUE_TEMPLATE/feature_request.md)
- [Tarea técnica](.github/ISSUE_TEMPLATE/technical_task.md)

Los issues sin ticket Jira o sin criterios de aceptación no se planifican.

## 10. Revisión del proceso

Este flujo, los owners y el SLA se revisan al final de cada sprint. Los dueños
del proceso son @Ameth-Toledo y @MelissaZarate08. Cualquier cambio en
`CODEOWNERS` requiere aprobación de todos los owners afectados y una prueba de
que GitHub sigue solicitando los revisores esperados.
