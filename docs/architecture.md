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
- Contratos anidados: los payloads son `@dataclass(frozen=True, slots=True)`
  o alias concretos (`JSONValue`); no se usan `dict[str, object]` ni `Any`
  como tipo del contrato. Los mappings transportados se entregan como
  `Mapping` inmutable (`MappingProxyType`) y las colecciones como tuplas, para
  que `frozen=True` no deje dicts anidados mutables. Los payloads compartidos
  por varios slices viven en `shared/application/dto/` (bbox, detection,
  event, observation, resolved track, monitor person y `FrameLike`) porque,
  de otro modo, cada feature duplicaría el mismo contrato de transporte.
- Excepción documentada: el frame crudo cruza como `FrameLike`, un Protocol
  estructural. En producción es un `numpy.ndarray`, pero el DTO no importa
  numpy: `validate_frame()` valida dtype y forma en la frontera del caso de uso
  (y `video_mapper` al codificar/decodificar).
- Imports permitidos en un DTO: stdlib/`typing`, re-exports de su propio
  paquete `application/dto` y `shared/application/dto`.
- Mappers: `application/mappers/` convierte DTO ↔ dominio y devuelve payloads
  tipados. La validación de formato, finitud y rango, y la conversión de tipos
  pesados viven ahí, no en el DTO.
- Serialización: `shared/application/dto/serialization.py` expone
  `to_json_value`/`dumps_json`. Los payloads `bytes` son de transporte (JPEG/
  PNG), se sirven como `image/jpeg` y `to_json_value` los sustituye por `null`
  en JSON (nunca viaja su contenido binario); los floats no finitos se
  rechazan con contexto.

La convención normativa está en
[ADR-0001, § Convención DTO](adr/0001-screaming-architecture-vertical-slice.md#convención-dto).

## Reglas automáticas

`tests/architecture/test_import_rules.py` verifica que:

- `shared/` no importe features ni infraestructura.
- El dominio de un feature no importe `application` ni `infrastructure`.
- `application/` no importe `infrastructure`.
- Un feature no importe la infraestructura de otro feature. Los imports
  relativos se resuelven a su ruta absoluta antes de evaluar estas reglas, así
  que `from ..infrastructure import ...` no las evade.
- Los DTOs solo importen stdlib/`typing`, su propio paquete `application/dto` y
  `shared/application/dto` (lista blanca).
- Los archivos `request_*.py`/`response_*.py` tengan la clase esperada, usen
  `@dataclass(frozen=True, slots=True)`, no contengan lógica y no usen
  `object`/`Any` en anotaciones de campo.
- Solo `main.py` puede importar más de un `*.infrastructure.dependencies`
  (composition root); el resto de raíces no puede concentrar factories.

`tests/architecture/test_dto_convention.py` verifica naming, decoradores,
ausencia de lógica y tipos concretos en los campos de todos los DTOs.

`tests/architecture/test_one_class_per_file.py` mantiene la política de una
clase de nivel superior por archivo.

Estos checks se ejecutan junto con toda la suite mediante `python -m pytest` en
cada pull request. Si un check falla, mueve la dependencia al límite correcto
(normalmente un port o un mapper) en lugar de relajar la regla.

La decisión arquitectónica y sus motivaciones están registradas en
[ADR-0001](adr/0001-screaming-architecture-vertical-slice.md).
