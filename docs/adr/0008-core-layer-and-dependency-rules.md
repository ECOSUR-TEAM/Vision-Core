# ADR 0008: Capa `core` y reglas de dependencia entre `features/`, `core/` y `scripts/`

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-21 |
| Tipo | Arquitectura / Deuda técnica |
| Prioridad | Alta |
| Ticket | ECM-105 |
| Etiquetas | `architecture`, `core`, `vertical-slice`, `adr`, `imports` |
| Dependencias | ADR 0001 (Screaming Architecture + Vertical Slice); ADR 0002 (persistencia y retención); ADR 0007 (registro de modelos) |
| Impacto | Base de los tickets 61–67; endurece los límites de imports al final del sprint |

## Contexto

Antes de ECM-111, `src/vision_core` exponía paquetes horizontales de primer nivel
además de `features/` y `scripts/`. ECM-106 migró el contenido compartido a
`core/` y ECM-111 eliminó los paquetes horizontales restantes: sus contenidos
viven en `core/config/`, `core/contracts/`, `core/inference/`,
`core/infrastructure/persistence/` y en los adaptadores de
`features/<slice>/infrastructure/`. Esa división mezclaba capas horizontales con
vertical slices: el mismo concepto podía vivir en dos árboles, había
implementaciones duplicadas y nada impedía un import de infraestructura hacia
features o de features hacia scripts. ECM-112 completó la migración del registro
de modelos a `core/model_registry/` y activó la prohibición total de los paths
antiguos.

ADR 0001 fijó el Vertical Slice dentro de cada feature y ADR 0002 fijó la
persistencia compartida. Esta decisión define el kernel transversal y las reglas
que impiden que las dependencias crezcan hacia capas horizontales o hacia los
scripts.

Esta decisión no renumera ADRs existentes: ADR 0003 sigue siendo el modelo de
ejecución multi-cámara y ADR 0007 el registro de modelos.

## Decisión

Adoptar `features/`, `core/` y `scripts/` como únicos paquetes de primer nivel de
`src/vision_core`, además de `__init__.py`. `core/` es el kernel compartido:
contratos y tipos estables que usen varios slices. `features/` contiene los
vertical slices del negocio. `scripts/` contiene herramientas de operación,
benchmark y calibración. El registro de modelos vive en `core/model_registry/`
según ADR 0007.

### Estructura vigente

```text
src/vision_core/
  core/                       # kernel compartido; no importa features ni scripts
    domain/                   # entidades y value objects transversales
    contracts/                # ports compartidos entre slices
    errors/                   # taxonomía de errores y códigos
    config/                   # configuración tipada y validada
    dto/                      # payloads de transporte compartidos
    serialization/            # JSON y conversión de payloads
    validation/               # validación reutilizable en fronteras
    inference/                # utilidades de inferencia compartidas
    telemetry/                # logging, métricas, health checks y profiling
    infrastructure/           # infraestructura compartida por varios slices
    model_registry/           # registro de modelos y model cards (ADR 0007)
  features/                   # vertical slices; cada uno con sus capas internas
    <slice>/
      application/
      domain/
      infrastructure/         # infraestructura específica del slice
  scripts/                    # herramientas; pueden importar features y core
```

Los submódulos de `core/` previstos en este ticket ya están poblados. ECM-106
migró aquí el contenido compartido (`domain/`, `dto/`, `errors/`, `inference/`,
`serialization/`, `telemetry/` y `validation/`). ECM-111 completó la limpieza de
los paquetes horizontales: la configuración pasó a `core/config/`, los ports y
repositorios a `core/contracts/`, el profiler a `core/telemetry/` y la
persistencia a `core/infrastructure/persistence/`; los adaptadores concretos
viven en `features/<slice>/infrastructure/`. ECM-112 movió el registro de modelos
a `core/model_registry/` y añadió el guard que mantiene el árbol final.

### Reglas de dependencia

| Origen | Destino permitido | Destino prohibido |
|---|---|---|
| `features/` | `core/`, otro `features/<slice>` mediante contratos públicos, stdlib y librerías de dominio | `scripts/`, infraestructura de otro slice |
| `scripts/` | `features/`, `core/`, stdlib y dependencias de operación | — |
| `core/` | `core/`, stdlib y dependencias del kernel | `features/`, `scripts/` |

En forma de reglas:

1. **`features → core`**: un feature puede y debe importar el kernel compartido.
   No importa `scripts/`.
2. **`scripts → features|core`**: los scripts son consumidores finales; pueden
   importar casos de uso, DTOs y contratos de los features, además de `core/`.
3. **`core` no importa `features` ni `scripts`**: las dependencias apuntan siempre
   hacia `core`, nunca desde `core` hacia afuera.
4. **Infraestructura específica de una feature** vive en
   `features/<slice>/infrastructure`. Otro slice no la importa; usa ports o DTOs
   del slice dueño.
5. **Infraestructura compartida** vive en `core/infrastructure` (por ejemplo,
   persistencia transversal). Un feature la consume mediante un contrato de
   `core/contracts` o `core/domain`, no importando implementaciones concretas de
   otro slice.
6. **DTOs de transporte compartidos** viven en `core/dto`. `core/domain` es kernel
   y no es un destino de imports desde DTOs; la conversión DTO ↔ dominio ocurre en
   mappers.

Ejemplos:

```python
# permitido, en features/door/application/use_cases/update_zone.py
from vision_core.core.dto import ObservationPayload
from vision_core.core.domain import Polygon

# permitido, en scripts/check_zones.py
from vision_core.features.door.application.use_cases.update_zone import UpdateZone
from vision_core.features.door.infrastructure.polygon_validation import validate_polygon

# prohibido, en cualquier módulo de core/
from vision_core.features.door.application.use_cases.update_zone import UpdateZone  # no

# prohibido, en features/ o core/
from vision_core.scripts.check_zones import main  # no
```

### Política de migración: sin shims nuevos

No se crean facades ni shims de compatibilidad. Cada ticket de la serie mueve el
código y actualiza imports, tests y documentación en el mismo cambio, dejando la
suite en verde. Los paths horizontales antiguos ya no existen: sus contenidos
están en `core/config/`, `core/contracts/`, `core/telemetry/`,
`core/inference/`, `core/infrastructure/persistence/`,
`core/model_registry/` y en los adaptadores de
`features/<slice>/infrastructure/`. `vision_core.shared` desapareció en ECM-106:
su contenido vive en `core/domain/`, `core/dto/`, `core/errors/`,
`core/inference/`, `core/serialization/`, `core/telemetry/` y `core/validation/`.
El HTML del monitor se sirve desde `features/monitor/infrastructure/http/static/`
desde ECM-110. ECM-112 activa reglas automáticas que fallan si reaparece
cualquiera de esos imports o si aparece una entrada de primer nivel fuera de
`core/`, `features/` y `scripts/`.

### Fuera de alcance

- Mover más módulos de producción a `core/` (salvo las migraciones ya completadas
  en ECM-106, ECM-111 y ECM-112).
- Reintroducir carpetas viejas: `application/`, `domain/`, `infrastructure/` y
  `settings/` ya se eliminaron en ECM-111.
- Cambiar el comportamiento de los imports públicos existentes.
- Modificar ADR 0001, ADR 0002, ADR 0003 ni ADR 0007.

## Consecuencias

### Positivas

- El árbol comunica el negocio (`features/`) y el kernel (`core/`) sin una capa
  horizontal que compita con los slices.
- `core/` no puede convertirse en un dominio global que importe features: la
  dirección de la dependencia es explícita.
- Los scripts dejan de ser un destino de imports desde código de producción.
- Los tests automáticos verifican el límite en cada cambio.

### Negativas y costes

- Los límites de `core/infrastructure` requieren revisión para no duplicar
  adaptadores que ya existen en un slice.

### Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| `core/` importe un feature "por comodidad" | Test estructural que prohíbe `vision_core.features` y `vision_core.scripts` dentro de `core/`. |
| `features/` importe un script de operación | Test estructural que prohíbe `vision_core.scripts` dentro de `features/`. |
| Se reintroduzcan shims para evitar actualizar imports | Política "sin shims nuevos" y revisión de cada diff del sprint. |
| Se reintroduzcan paths horizontales eliminados | Tests parametrizados de imports y test de contenido permitido de `src/vision_core`. |
| Se reintroduzcan shims de paths viejos | Revisión de diffs y regla "sin shims nuevos"; ningún path legacy queda declarado en código, tests, docs ni configuración. |

## Alternativas consideradas

1. **Mantener los paquetes actuales y añadir reglas de imports.** Descartada:
   no resuelve la duplicación ni la mezcla de capas horizontales con slices.
2. **Crear una capa `common/` además de `core/`.** Descartada: traslada el
   problema y añade otro nombre ambiguo.

## Verificación

- `tests/architecture/test_import_rules.py` verifica que `core/` no importa
  `features/` ni `scripts/`, que `scripts/` no es importado por `features/` ni
  `core/`, que no quedan imports de paquetes horizontales antiguos y que los DTOs
  no importan dominio, infraestructura ni frameworks.
- `tests/architecture/test_one_class_per_file.py` y
  `tests/test_one_class_per_file.py` incluyen `src/vision_core` de forma
  recursiva, por lo que cubren `core/`.
- `tests/architecture/test_dto_convention.py` y
  `tests/contracts/test_dto_boundary_contract.py` tratan `core/dto` como path
  legítimo de transporte, con los mismos invariantes que el resto de DTOs.
- ECM-112 prohíbe todos los paths horizontales antiguos, incluido el antiguo
  path del registro de modelos, y valida que el contenido de primer nivel de
  `src/vision_core` sea solo `__init__.py`, `core/`, `features/` y `scripts/`.
- Validar con `PYTHONPATH=.:src python -m pytest -q --no-cov`,
  `python -m mypy --config-file pyproject.toml --no-site-packages`,
  `python -m ruff check .` y `python -m ruff format --check .`.

## Enmiendas

| Fecha | Cambio | Motivo | ADR que la motiva |
|---|---|---|---|
| 2026-11-21 | Creación del ADR | Contrato de capas ECM-105 | — |
| 2026-11-22 | Migración del paquete compartido a `core/` completada (ECM-106, PR #109, commit `cb9b128`): `domain/`, `dto/`, `errors/`, `inference/`, `serialization/`, `telemetry/` y `validation/`; el path compartido legacy eliminado | Implementación del contrato de capas | ADR 0008 |
| 2026-11-22 | ECM-111 completa la limpieza legacy: desaparecen los paquetes horizontales de primer nivel; su contenido vive en `core/config/`, `core/contracts/`, `core/inference/`, `core/infrastructure/persistence/` y adaptadores de `features/<slice>/infrastructure/` | Finalización de la migración de paquetes de primer nivel | ADR 0008 |
| 2026-11-23 | ECM-107 mueve `frame_profiler.py` de `core/inference/` a `core/telemetry/`; se actualizan imports, tests, umbrales de cobertura y documentación | Migrar `settings/` y `application/` a `core/config` y `core/telemetry` | ADR 0008 |
| 2026-11-23 | El path `vision_core.core.inference.frame_profiler` queda eliminado sin shim; el import público canónico es `from vision_core.core.telemetry import FrameProfiler, STAGES` | Romper el path legacy de forma explícita tras la migración | ADR 0008 |
| 2026-11-23 | ECM-108 consolida `ReIDMemory` como `Protocol` canónico en `core/contracts`, elimina el `Protocol` duplicado del slice y actualiza todos los imports | Contrato único compartido entre slices sin identidades de clase duplicadas | ADR 0008 |
| 2026-11-23 | El path `vision_core.features.reid.domain.ports.reid_memory` queda eliminado sin shim; el import público canónico es `from vision_core.core.contracts import ReIDMemory` | Cumplir la política de migración sin facades ni re-exports | ADR 0008 |
| 2026-11-23 | ECM-110 confirma el fin del paquete horizontal de infraestructura: el HTML del monitor vive en `features/monitor/infrastructure/http/static/`, `package-data` apunta a ese paquete y los adaptadores/CLI permanecen en sus slices o en `scripts/` | Infraestructura feature-specific, sin shims de compatibilidad | ADR 0008 |
| 2026-11-23 | ECM-112 mueve el registro de modelos a `core/model_registry/`, activa guardrails para todos los paths horizontales antiguos y restringe el contenido de primer nivel de `src/vision_core` | Cierre final del Sprint 10 con el árbol prohibido por tests | ADR 0008 |
