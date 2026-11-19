# Arquitectura y límites de imports

Vision Core usa Vertical Slice: cada feature es dueño de sus casos de uso,
dominio y adaptadores. `shared/` contiene únicamente tipos estables y
transversales; no debe convertirse en un segundo dominio global.

## Estructura de tests

Los tests espejo viven bajo `tests/features/<feature>/{application,domain,infrastructure}`.
Los tests transversales están en `tests/integration/`, `tests/evaluation/` y
`tests/shared/`; los dobles reutilizables están en `tests/fakes/`.

## Convención DTO

Cada operación pública del slice se expresa con un DTO de request y, cuando
devuelve datos, uno de response. No se crea un `dto/` global: los DTOs son
propiedad de su feature y solo se mueven a `shared/application/dto/` si varios
slices comparten el contrato y el movimiento queda justificado.

- Ubicación:
  `features/<feature>/application/dto/request/request_<operacion>.py` y
  `features/<feature>/application/dto/response/response_<operacion>.py`.
- Naming: `request_<operacion>.py` define `Request<Operacion>` y
  `response_<operacion>.py` define `Response<Operacion>`; una clase por archivo.
- Declaración: `@dataclass(frozen=True, slots=True)`, sin lógica de negocio.
- Contenido: solo datos y tipos transportables de stdlib o `typing`. No se
  importan `numpy`, `cv2`, `torch`, `domain/` ni `infrastructure/`.
- Imports permitidos en un DTO: stdlib/`typing`, re-exports de su propio
  paquete `application/dto` y, si existe, `shared/application/dto/base.py`.
- Mappers: `application/mappers/` convierte DTO ↔ dominio. La validación de
  formato y la conversión de tipos pesados viven ahí, no en el DTO.
- Serialización: `dataclasses.asdict(...)` y `json.dumps(..., allow_nan=False)`
  cuando el contrato viaja como JSON. Los payloads binarios se transportan como
  `bytes` y se excluyen de la serialización JSON.

La convención normativa está en
[ADR-0001, § Convención DTO](adr/0001-screaming-architecture-vertical-slice.md#convención-dto).

## Reglas automáticas

`tests/architecture/test_import_rules.py` verifica que:

- `shared/` no importe features ni infraestructura.
- El dominio de un feature no importe `application` ni `infrastructure`.
- `application/` no importe `infrastructure`.
- Un feature no importe la infraestructura de otro feature.
- Los DTOs solo importen stdlib/`typing`, su propio paquete `application/dto` y,
  si existe, `shared/application/dto` (lista blanca).
- Los archivos `request_*.py`/`response_*.py` tengan la clase esperada, usen
  `@dataclass(frozen=True, slots=True)` y no contengan lógica.

`tests/architecture/test_dto_convention.py` verifica naming, decoradores y
ausencia de lógica en todos los DTOs.

`tests/architecture/test_one_class_per_file.py` mantiene la política de una
clase de nivel superior por archivo.

Estos checks se ejecutan junto con toda la suite mediante `python -m pytest` en
cada pull request. Si un check falla, mueve la dependencia al límite correcto
(normalmente un port o un mapper) en lugar de relajar la regla.

La decisión arquitectónica y sus motivaciones están registradas en
[ADR-0001](adr/0001-screaming-architecture-vertical-slice.md).
