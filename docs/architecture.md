# Arquitectura y límites de imports

Vision Core usa Vertical Slice: cada feature es dueño de sus casos de uso,
dominio y adaptadores. `core/` contiene únicamente el kernel compartido; no debe
convertirse en un segundo dominio global. `shared/` ya fue eliminado y su
contenido migró a `core/` (ECM-106). Los antiguos paquetes de primer nivel
`application/`, `domain/`, `infrastructure/` y `settings/` fueron eliminados por
ECM-111; solo `model_registry/` permanece como excepción transitoria (ADR 0007,
ticket 67). El kernel, los contratos y la infraestructura comunes viven en
`core/` (ADR 0008).

## Estructura

El árbol de `src/vision_core/` tiene tres paquetes de primer nivel, más
`model_registry/` como excepción transitoria:

```text
src/vision_core/
  core/
    domain/
    contracts/
    errors/
    config/
    dto/
    serialization/
    validation/
    inference/
    telemetry/
    infrastructure/
  model_registry/               # ADR 0007; excepción transitoria, ticket 67
  features/
    <slice>/application/
    <slice>/domain/
    <slice>/infrastructure/
  scripts/
```

`core/` es el destino del kernel compartido: dominio y contratos transversales,
errores, configuración, DTOs y serialización compartidos, validación, inferencia,
telemetría e infraestructura compartida. La infraestructura específica de un
feature permanece en `features/<slice>/infrastructure`; la compartida por varios
slices vive en `core/infrastructure`. `model_registry/` se migrará a
`core/model_registry/` en el ticket 67.

## Reglas de capas

| Origen | Puede importar | No puede importar |
|---|---|---|
| `features/` | `core/`, contratos públicos de otro slice | `scripts/`, infraestructura de otro slice |
| `scripts/` | `features/`, `core/` | — |
| `core/` | `core/` y dependencias del kernel | `features/`, `scripts/` |

Ejemplos permitidos:

```python
from vision_core.core.dto import ObservationPayload
from vision_core.features.door.application.use_cases.update_zone import UpdateZone
```

Ejemplos prohibidos:

```python
from vision_core.features.door.domain.entities.polygon import Polygon  # en core/
from vision_core.scripts.check_zones import main  # en features/ o core/
from vision_core.features.monitor.infrastructure.state import MonitorState  # en otro slice
```

La decisión completa, incluida la política "sin shims nuevos" y el diferimiento
de la prohibición de `model_registry/` al ticket 67, está en
[ADR 0008](adr/0008-core-layer-and-dependency-rules.md).

## Estructura de tests

Los tests espejo viven bajo `tests/features/<feature>/{application,domain,infrastructure}`.
Los tests transversales están en `tests/architecture/`, `tests/contracts/`,
`tests/integration/`, `tests/evaluation/`, `tests/performance/`,
`tests/regression/` y `tests/e2e/`; los dobles reutilizables están en
`tests/fakes/`.

## Convención DTO

Cada operación pública del slice se expresa con un DTO de request y, cuando
devuelve datos, uno de response. No se crea un `dto/` global de operaciones: los
DTOs son propiedad de su feature y solo se mueven a `core/dto/` si varios slices
comparten el contrato y el movimiento queda justificado. `core/dto/` es path
legítimo de transporte; `core/domain/` es kernel y no es destino de imports
desde DTOs.

- Ubicación:
  `features/<feature>/application/dto/request/request_<operacion>.py` y
  `features/<feature>/application/dto/response/response_<operacion>.py`.
- Naming: `request_<operacion>.py` define `Request<Operacion>` y
  `response_<operacion>.py` define `Response<Operacion>`; una clase por archivo.
- Declaración: `@dataclass(frozen=True, slots=True)`, sin lógica de negocio.
- Contenido: solo datos y tipos transportables de stdlib o `typing`. No se
  importan `numpy`, `cv2`, `torch`, ni módulos de dominio o infraestructura.
- Contratos anidados: los payloads son `@dataclass(frozen=True, slots=True)`
  o alias concretos (`JSONValue`); no se usan `dict[str, object]` ni `Any`
  como tipo del contrato. Los mappings transportados se entregan como
  `Mapping` inmutable (`MappingProxyType`) y las colecciones como tuplas, para
  que `frozen=True` no deje dicts anidados mutables. Los payloads compartidos
   por varios slices viven en `core/dto/` (bbox, detection, event,
   observation, resolved track, monitor person y `FrameLike`) porque,
   de otro modo, cada feature duplicaría el mismo contrato de transporte.

- Excepción documentada: el frame crudo cruza como `FrameLike`, un Protocol
  estructural. En producción es un `numpy.ndarray`, pero el DTO no importa
  numpy: `validate_frame()` valida dtype y forma en la frontera del caso de uso
  (y `video_mapper` al codificar/decodificar).
- Imports permitidos en un DTO: stdlib/`typing`, re-exports de su propio
  paquete `application/dto` y `core/dto`.
- Mappers: `application/mappers/` convierte DTO ↔ dominio y devuelve payloads
  tipados. La validación de formato, finitud y rango, y la conversión de tipos
  pesados viven ahí, no en el DTO.
- Serialización: `core/serialization/serialization.py` expone
  `to_json_value`/`dumps_json`. Los payloads `bytes` son de transporte (JPEG/
  PNG), se sirven como `image/jpeg` y `to_json_value` los sustituye por `null`
  en JSON (nunca viaja su contenido binario); los floats no finitos se
  rechazan con contexto.

La convención normativa está en
[ADR-0001, § Convención DTO](adr/0001-screaming-architecture-vertical-slice.md#convención-dto).

## Reglas automáticas

`tests/architecture/test_import_rules.py` verifica que:

- No queden imports de `vision_core.shared` ni el paquete `shared/`.
- El dominio de un feature no importe `application` ni `infrastructure`.
- `application/` no importe `infrastructure`.
- Un feature no importe la infraestructura de otro feature. Los imports
  relativos se resuelven a su ruta absoluta antes de evaluar estas reglas, así
  que `from ..infrastructure import ...` no las evade.
- Los DTOs solo importen stdlib/`typing`, su propio paquete `application/dto` y
  `core/dto` (lista blanca).
- `core/` no importe `features/` ni `scripts/`.
- `features/` y `core/` no importen `scripts/`.
- Los archivos `request_*.py`/`response_*.py` tengan la clase esperada, usen
  `@dataclass(frozen=True, slots=True)`, no contengan lógica y no usen
  `object`/`Any` en anotaciones de campo.
- Solo `main.py` puede importar más de un `*.infrastructure.dependencies`
  (composition root); el resto de raíces no puede concentrar factories.
  Instrumentar G0 no crea nuevos composition roots ni workers: `main.py` sigue
  siendo el único punto de ensamblado mientras ADR-0003 (multi-cámara) no se
  levante.

`tests/architecture/test_dto_convention.py` verifica naming, decoradores,
ausencia de lógica y tipos concretos en los DTOs de features y `core/dto/`.

`tests/architecture/test_one_class_per_file.py` mantiene la política de una
clase de nivel superior por archivo.

Estos checks se ejecutan junto con toda la suite mediante `python -m pytest` en
cada pull request. Si un check falla, mueve la dependencia al límite correcto
(normalmente un port o un mapper) en lugar de relajar la regla.

Los repository ports transversales viven en
`vision_core.core.contracts` y sus implementaciones SQLite en
`vision_core.core.infrastructure.persistence`; el dominio no conoce SQL.
`main.py` inyecta los adaptadores y hace degradar la persistencia ante errores sin
detener el video.

Las decisiones arquitectónicas y sus motivaciones están registradas en
[ADR-0001](adr/0001-screaming-architecture-vertical-slice.md),
[ADR-0002](adr/0002-persistence-and-retention.md),
[ADR-0003](adr/0003-modelo-ejecucion-multi-camara.md),
[ADR-0007](adr/0007-registro-de-modelos-y-model-cards.md) y
[ADR-0008](adr/0008-core-layer-and-dependency-rules.md).
