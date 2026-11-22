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

Hoy `src/vision_core` expone `application/`, `domain/`, `infrastructure/`,
`settings/` y `model_registry/` como paquetes de primer nivel, además de
`features/` y `scripts/`. `shared/` era otro paquete de primer nivel, pero ECM-106
ya migró su contenido a `core/` y el path `vision_core.shared` ha desaparecido.
Esa división mezcla capas horizontales con vertical slices: el mismo concepto
puede vivir en dos árboles, hay implementaciones duplicadas y nada impide un
import de `infrastructure → features` o de `features → scripts`.
`model_registry/` es un path transitorio introducido por ADR 0007; su destino
final es `core/model_registry/`.

ADR 0001 fijó el Vertical Slice dentro de cada feature y ADR 0002 fijó la
persistencia compartida. Ninguno de los dos definió un único lugar para el kernel
transversal ni una regla que impida que las dependencias vuelvan a crecer hacia
las capas horizontales antiguas. El objetivo del sprint es que el árbol final
tenga solo tres paquetes de primer nivel: `features/`, `core/` y `scripts/`.

Esta decisión no renumera ADRs existentes: ADR 0003 sigue siendo el modelo de
ejecución multi-cámara y ADR 0007 el registro de modelos.

## Decisión

Adoptar `features/`, `core/` y `scripts/` como únicos paquetes de primer nivel de
`src/vision_core`. `core/` es el kernel compartido: contratos y tipos estables que
usen varios slices. `features/` contiene los vertical slices del negocio.
`scripts/` contiene herramientas de operación, benchmark y calibración.

### Árbol objetivo

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
    telemetry/                # logging, métricas y health checks
    infrastructure/           # infraestructura compartida por varios slices
    model_registry/           # registro de modelos y model cards (ADR 0007)
  features/                   # vertical slices; cada uno con sus capas internas
    <slice>/
      application/
      domain/
      infrastructure/         # infraestructura específica del slice
  scripts/                    # herramientas; pueden importar features y core
```

Los submódulos de `core/` se crean vacíos en este ticket, salvo el código que ya
existe en `model_registry/` y que se migrará desde su path transitorio. Solo
recibirán más código cuando un ticket de migración lo mueva desde los paquetes
actuales; ECM-106 ya migró aquí el contenido de `shared/` (`domain/`, `dto/`,
`errors/`, `inference/`, `serialization/`, `telemetry/` y `validation/`).

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
suite en verde. Los paths antiguos (`vision_core.application`,
`vision_core.domain`, `vision_core.infrastructure`, `vision_core.settings` y
`vision_core.model_registry`) siguen existiendo durante el sprint, pero se
eliminan en la limpieza final: el ticket 67 activa las reglas que prohíben
importarlos. `vision_core.shared` ya no existe: ECM-106 migró su contenido a
`core/domain/`, `core/dto/`, `core/errors/`, `core/inference/`,
`core/serialization/`, `core/telemetry/` y `core/validation/`. Este ADR no añade
aún esas reglas para no romper la migración incremental.

### Fuera de alcance

- Mover módulos de producción a `core/` (salvo la migración de `shared/`
  completada en ECM-106, el esqueleto vacío de este ticket y la migración
  posterior de `model_registry/`).
- Eliminar carpetas viejas.
- Cambiar el comportamiento de los imports públicos existentes.
- Modificar ADR 0001, ADR 0002, ADR 0003 ni ADR 0007.

## Consecuencias

### Positivas

- El árbol comunica el negocio (`features/`) y el kernel (`core/`) sin una capa
  horizontal que compita con los slices.
- `core/` no puede convertirse en un segundo `shared/` ni en un dominio global
  que importe features: la dirección de la dependencia es explícita.
- Los scripts dejan de ser un destino de imports desde código de producción.
- Cada ticket puede migrar un módulo y verificar el límite con tests automáticos.

### Negativas y costes

- Durante el sprint conviven los paquetes viejos con los nuevos; la suite no puede
  prohibir los paths viejos hasta el ticket 67.
- Los imports de módulos movidos deben actualizarse en el mismo cambio; no hay una
  capa de compatibilidad que amortigüe el salto.
- Los límites de `core/infrastructure` requieren revisión para no duplicar
  adaptadores que ya existen en un slice.

### Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| `core/` importe un feature "por comodidad" | Test estructural que prohíbe `vision_core.features` y `vision_core.scripts` dentro de `core/`. |
| `features/` importe un script de operación | Test estructural que prohíbe `vision_core.scripts` dentro de `features/`. |
| Se reintroduzcan shims para evitar actualizar imports | Política "sin shims nuevos" y revisión de cada diff del sprint. |
| Las reglas de paths viejos se activen antes de tiempo | Reglas de prohibición de `domain`, `application`, `settings`, `infrastructure` y `model_registry` diferidas al ticket 67; `shared` ya se eliminó en ECM-106. |

## Alternativas consideradas

1. **Mantener los paquetes actuales y añadir reglas de imports.** Descartada:
   no resuelve la duplicación ni la mezcla de capas horizontales con slices.
2. **Crear una capa `common/` además de `shared/`.** Descartada: traslada el
   problema y añade otro nombre ambiguo.
3. **Añadir facades temporales en `core/` que reexporten los paquetes viejos.**
   Descartada: contradice la política "sin shims nuevos" y ocultaría la deuda.

## Verificación

- `tests/architecture/test_import_rules.py` verifica que `core/` no importa
  `features/` ni `scripts/`, que `scripts/` no es importado por `features/` ni
  `core/`, que no quedan imports de `vision_core.shared` y que los DTOs no
  importan dominio, infraestructura ni frameworks.
- `tests/architecture/test_one_class_per_file.py` y
  `tests/test_one_class_per_file.py` incluyen `src/vision_core` de forma
  recursiva, por lo que cubren `core/`.
- `tests/architecture/test_dto_convention.py` y
  `tests/contracts/test_dto_boundary_contract.py` tratan `core/dto` como path
  legítimo de transporte, con los mismos invariantes que el resto de DTOs.
- La prohibición de los paths viejos, incluido `vision_core.model_registry`, se
  difiere al ticket 67 y no se activa en este ADR; `vision_core.shared` ya fue
  eliminado por ECM-106.
- Validar con `PYTHONPATH=.:src python -m pytest -q --no-cov`,
  `python -m mypy --config-file pyproject.toml --no-site-packages`,
  `python -m ruff check .` y `python -m ruff format --check .`.

## Enmiendas

| Fecha | Cambio | Motivo | ADR que la motiva |
|---|---|---|---|
| 2026-11-21 | Creación del ADR | Contrato de capas ECM-105 | — |
| 2026-11-22 | Migración de `shared/` a `core/` completada (ECM-106, PR #109, commit `cb9b128`): `domain/`, `dto/`, `errors/`, `inference/`, `serialization/`, `telemetry/` y `validation/`; `vision_core.shared` eliminado | Implementación del contrato de capas | ADR 0008 |
