# ADR 0001: Screaming Architecture + Vertical Slice con capas por feature y DTOs

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-17 |
| Tipo | Arquitectura / Decisión |
| Prioridad | Alta |
| Ticket | ECM-58 |
| Etiquetas | `architecture`, `adr`, `vertical-slice`, `screaming`, `dto`, `clean-architecture` |
| Dependencias | Tickets 1–12 completados |
| Impacto | Prerrequisito de todos los tickets del sprint 4 |

## Contexto

Hoy el proyecto está organizado por capas horizontales globales: `domain/`,
`application/` e `infrastructure/`, con `main.py` en la raíz y `composition.py`
como punto de composición adicional. Los dominios del negocio (video, detección,
ReID, puerta/zonas, monitor y pipeline) están repartidos entre esas tres
carpetas: para entender un solo caso de uso hay que recorrer árboles distintos.

El estado real del repositorio al momento de esta decisión es:

- `domain/model/` contiene los conceptos compartidos y también conceptos que
  pertenecen a un solo feature (`Detection`, `ResolvedTrack`).
- `domain/ports/` contiene los cuatro contratos externos globales.
- `infrastructure/` tiene subcarpetas por dominio, pero ninguna expone casos de
  uso propios: la orquestación vive en `application/vision_core_app.py`.
- No existe `src/`, ni `features/`, ni DTOs; los límites entre capas se verifican
  hoy con pruebas estructurales (`tests/test_composition.py`,
  `tests/application/test_pipeline_integration.py`,
  `tests/test_one_class_per_file.py`).
- El dominio no depende de NumPy, OpenCV ni PyTorch, y rige la convención de una
  clase por archivo (ECM-44, ECM-54).

Los problemas de este layout son: (1) la estructura no comunica el negocio, sino
la técnica; (2) un cambio en un feature toca tres raíces distintas; (3) no hay
un contrato de transporte explícito entre casos de uso y el exterior, por lo que
tipos de infraestructura pueden filtrarse hacia `application/`; (4) agregar un
feature nuevo obliga a decidir dónde va cada archivo en tres capas globales.

Esta decisión es prerrequisito de los tickets del sprint 4, entre ellos los de
migración ECM-60, ECM-61, ECM-64 y ECM-65, y debe quedar registrada antes de que
esos tickets migren código.

## Decisión

Adoptar **Vertical Slice organizada por Screaming Architecture**, manteniendo
**Clean Architecture dentro de cada feature**. La estructura debe "gritar" el
negocio: `video`, `detection`, `reid`, `door`, `monitor`, `pipeline`.

- `main.py` **se queda en la raíz** como composition root y entrypoint
  obligatorio. Toda la aplicación vive en `src/vision_core/`.
- Cada feature es autocontenido con sus capas `application/`, `domain/` e
  `infrastructure/`. Solo se crean las carpetas que tengan contenido real.
- Cada slice se comunica con otros slices únicamente mediante contratos
  públicos: ports, DTOs o casos de uso. Nunca importa la infraestructura de otro
  feature.
- La migración es incremental (strangler), feature por feature, con la suite de
  pruebas en verde después de cada slice.

### Estructura objetivo

```text
main.py                         # composition root / entrypoint (raíz, obligatorio)
src/
  vision_core/
    settings.py                 # env/config
    shared/
      domain/
        bbox.py
        polygon.py
        event.py
        event_type.py
      application/
        dto/
          base.py               # base/protocolos opcionales
    features/
      detection/
        application/
          dto/
            request/
              request_detector.py
            response/
              response_detector.py
          use_cases/
            detect_persons.py   # clase DetectPersons
          mappers/
            detection_mapper.py
        domain/
          entities/
            detection.py
          ports/
            detector_manager.py
        infrastructure/
          adapters/
            yolo_detector_manager.py
            track.py
            iou.py
          dependencies.py       # factory/DI del feature
      video/
        application/
          dto/request/... dto/response/...
          use_cases/...
          mappers/...
        domain/
          ports/video_source.py
        infrastructure/
          adapters/rtsp_video_source.py
          adapters/file_video_source.py
          adapters/latest_frame_source.py
          dependencies.py
      reid/
        application/
          dto/request/... dto/response/...
          use_cases/...
          mappers/...
        domain/
          entities/... (si aplica)
          ports/reid_memory.py
        infrastructure/
          adapters/memory_reid.py
          adapters/embedder.py
          dependencies.py
      door/
        application/
          dto/request/... dto/response/...
          use_cases/...
          mappers/...
        domain/
          ports/door_analytics.py
        infrastructure/
          adapters/polygon_door_analytics.py
          adapters/uncalibrated_analytics.py
          config/zone_config.py
          config/zone_loader.py
          geometry.py
          dependencies.py
      monitor/
        application/
          dto/request/... dto/response/...
          use_cases/...
          mappers/...
        domain/
          ports/... (solo si hay contrato real)
        infrastructure/
          state.py
          renderer.py
          http/handler.py
          http/server.py
          dependencies.py
      pipeline/
        application/
          dto/request/... dto/response/...
          use_cases/run_pipeline.py   # ex VisionCoreApp
          mappers/...
        domain/
          entities/resolved_track.py
          ports/... (si aplica)
        infrastructure/
          dependencies.py
```

La convención de una clase por archivo (ECM-54) se mantiene dentro de este
árbol; los `...` del árbol indican archivos que se crearán cuando el feature
tenga operaciones reales, no carpetas vacías.

### Decisión sobre `data/`

**No se crea una carpeta `data/` como capa dentro de los features.** El nombre
es ambiguo (¿datos de entrada, persistencia, fixtures, modelos?) y suele
duplicar infraestructura. Reglas de ubicación:

| Tipo de dato | Ubicación |
|---|---|
| Persistencia (DB, archivos, caché) | `features/<feature>/infrastructure/persistence/` |
| Clientes externos (cámara, modelo, APIs) | `features/<feature>/infrastructure/adapters/` o `external/` |
| Contratos de persistencia | `features/<feature>/domain/repositories/` **solo si existe persistencia real** |
| Contratos de servicios externos (cámara, detector, ReID, analítica) | `features/<feature>/domain/ports/` |
| Datos estáticos, fixtures o muestras | `data/` o `tests/fixtures/` en la raíz, **nunca** dentro de un feature |

No se crean carpetas vacías: si un feature no tiene persistencia, no existe
`repositories/` ni `persistence/`. Los archivos de configuración de ejemplo
(`config/zones.example.json`, `config/frigate.*.yml`) y los pesos de modelos no
son código del feature y permanecen fuera de `src/vision_core/`.

### Responsabilidades por capa

| Capa | Contenido | Restricciones |
|---|---|---|
| `domain/` | Entidades y value objects puros, `ports/` (contratos de servicios externos) y `repositories/` (solo persistencia real) | Sin frameworks, sin `numpy`, sin `cv2`, sin `torch`. No importa `application/` ni `infrastructure/`. |
| `application/` | Casos de uso (`use_cases/`), DTOs (`dto/request`, `dto/response`) y mappers | Depende solo de `domain/`. No importa `infrastructure/`. Sin frameworks. |
| `infrastructure/` | Adaptadores concretos que implementan ports/repositorios, clientes externos y persistencia | Puede importar `domain/` y, en el factory del feature, `application/use_cases`. No importa infraestructura de otros features. |
| `dependencies.py` | Inyección de dependencias del feature: construye sus casos de uso con sus adaptadores | Recibe configuración/dependencias externas por parámetro. No importa infraestructura de otros features. |

### Convención DTO

- Ubicación:
  `features/<feature>/application/dto/request/request_<operacion>.py` y
  `features/<feature>/application/dto/response/response_<operacion>.py`.
- Nombres: `RequestDetector` / `ResponseDetector` en el ejemplo de detección;
  si hay varias operaciones, `RequestProcessFrame` / `ResponseProcessFrame`,
  etc. Un DTO por operación y sentido.
- Inmutables: `@dataclass(frozen=True, slots=True)`, sin lógica de negocio.
- Solo tipos serializables y transportables (stdlib y `typing`). Sin `numpy`,
  `cv2`, `torch`, ni imports de `domain/` o `infrastructure/`. Los campos
  anidados son payloads inmutables (`@dataclass(frozen=True, slots=True)`) o
  alias concretos (`JSONValue`); `dict[str, object]` y `Any` no forman parte del
  contrato.
- Excepción documentada: el frame crudo se anota como `FrameLike` (Protocol
  estructural). En producción es un `numpy.ndarray`, pero el DTO no importa
  numpy: `video_mapper` valida dtype y forma en la frontera.
- Los mappers viven en `application/mappers/` y convierten DTO ↔ dominio,
  devolviendo payloads tipados. Un mapper no importa adaptadores concretos y
  valida finitud/rango antes de convertir.
- La lista blanca de imports es: stdlib/`typing`, re-exports del propio paquete
  `application/dto` y `shared/application/dto`. Todo lo demás (dominio,
  infraestructura, frameworks de visión u otros features) queda fuera del DTO.
- La serialización JSON usa `shared/application/dto/serialization.py`
  (`to_json_value`/`dumps_json`, con `allow_nan=False`). Los payloads binarios
  viajan como `bytes`, se sirven como `image/jpeg` y se omiten del JSON.
- No existe un `dto/` global de operaciones. Los payloads compartidos por
  varios slices (bbox, event, observation, track, monitor person) viven en
  `shared/application/dto/` para no duplicar el contrato en cada feature.

La guía practica y los ejemplos de esta convención están en
[`docs/architecture.md`](../architecture.md#convención-dto).

Los DTOs son el contrato de transporte del slice: el composition root y los
demás features hablan con casos de uso mediante DTOs; los tipos ricos del
dominio no cruzan ese borde.

### Reglas de dependencia

1. `shared/` no importa `features/`.
2. `features/<X>/domain` no importa `application` ni `infrastructure`.
3. `features/<X>/application` no importa `infrastructure`.
4. `features/<X>` no importa `features/<Y>/infrastructure`; solo puede usar
   contratos públicos (ports, DTOs, casos de uso).
5. `main.py` (raíz) es el composition root: importa los `dependencies.py` de
   cada feature y cablea todo.
6. No se permiten ciclos de imports.

Si un tipo se usa en un solo feature, no va a `shared/`. `shared/` contiene
únicamente kernel compartido por varios slices.

### Inyección de dependencias

- Manual, sin framework de DI, coherente con el proyecto actual.
- Cada feature expone `infrastructure/dependencies.py` con una función
  `build_<feature>(...)`.
- `main.py` llama a esas funciones y pasa las dependencias entre features; por
  ejemplo, el `DetectorManager` de detection se inyecta en el pipeline.
- Los features no auto-instancian adaptadores globales ni leen `os.environ`
  directamente: reciben la configuración desde el composition root, que la
  obtiene de `src/vision_core/settings.py`.
- Los adaptadores costosos (modelos, cámaras) se importan de forma diferida en
  los builders, como hoy en `composition.py`, para que importar la aplicación
  no cargue pesos ni abra conexiones.

### Estrategia de migración

- Patrón **strangler**: introducir `src/vision_core/`, luego migrar feature por
  feature. El orden acordado es shared → detection → door → monitor → video →
  reid → pipeline.
- Se permiten shims temporales para no romper imports; se eliminan en el ticket
  24 de la secuencia de migración (limpieza de shims).
- Cada slice migrado actualiza sus tests y deja la suite verde antes de migrar
  el siguiente. Los tests viejos se reubican junto al slice, no se duplican.
- Estado de los slices (la implementación efectiva se registra en los tickets
  indicados; este ADR solo fija la decisión):

| Slice | Ticket de migración | Estado |
|---|---|---|
| `shared/` | ECM-60 | Definido; ver mapa de migración |
| `features/detection/` | ECM-61 | Definido; ver mapa de migración |
| `features/door/` | ECM-64 | Definido; ver mapa de migración |
| `features/monitor/` | ECM-65 | Definido; ver mapa de migración |
| `features/video/` | Pendiente de ticket | Solo destino definido en este ADR |
| `features/reid/` | Pendiente de ticket | Solo destino definido en este ADR |
| `features/pipeline/` | Pendiente de ticket | Solo destino definido en este ADR |

## Consecuencias

### Positivas

- La estructura comunica el negocio: al abrir `features/` se ven los dominios
  del sistema, no las capas técnicas.
- Un cambio en un feature queda confinado a su carpeta; el acoplamiento entre
  features pasa a ser explícito y revisable.
- Los DTOs congelan el contrato de transporte: no hay tipos de NumPy, OpenCV o
  PyTorch cruzando hacia `application/`.
- El dominio sigue libre de frameworks y de dependencias pesadas.
- Los tests pueden organizarse por slice (`tests/features/<feature>/`), con lo
  que una prueba describe un caso de uso completo.
- `main.py` sigue siendo el único lugar que decide qué implementaciones
  concretas se usan.

### Negativas y costes

- Más archivos y paquetes (`__init__.py`, DTOs, mappers, `dependencies.py`)
  para el mismo caso de uso.
- Cierta duplicación de tipos entre dominio y DTO es deliberada; los mappers
  pagan ese coste una vez por operación.
- La migración temporal tiene shims y rutas antiguas y nuevas conviviendo.
- Hay que reforzar las pruebas estructurales para las reglas nuevas; hoy solo
  se verifican las reglas globales antiguas.

### Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| `domain/` empiece a importar `application/` o `infrastructure/` | Tests estructurales por slice y revisión de diffs. |
| DTOs con `numpy`, `cv2`, `torch` o imports de dominio | Convención de esta sección, lista blanca en `test_import_rules.py`, check global en `test_dto_convention.py` y test de contrato por slice. |
| Importaciones cruzadas entre features | Regla 4; los features solo comparten ports, DTOs o casos de uso. |
| Carpetas vacías o `data/` dentro de un feature | Regla "solo contenido real" y decisión sobre `data/`. |
| Features leyendo variables de entorno | `settings.py` + configuración inyectada desde `main.py`. |
| Ciclos de imports | Un único sentido de dependencia: infrastructure → application → domain. |

## Alternativas consideradas

1. **Mantener las capas horizontales globales.** Descartada: no escala con
   nuevos features y la estructura no expresa el negocio.
2. **Vertical Slice sin capas internas** (todo el feature en un paquete plano).
   Descartada: pierde las garantías de Clean Architecture y las reglas de
   dependencia ya existentes.
3. **Crear una capa `data/` por feature.** Descartada: nombre ambiguo y duplica
   `infrastructure/`; se sustituye por las reglas de la sección anterior.
4. **Framework de inyección de dependencias.** Descartada: el proyecto ya resuel-
   ve la composición a mano y agregar un framework no aporta en este tamaño.

## Verificación

- La suite sigue siendo la referencia: `python -m pytest -q`.
- `tests/architecture/test_import_rules.py` verifica los límites de imports y
  la lista blanca de imports de los DTOs.
- `tests/architecture/test_dto_convention.py` verifica naming, decoradores y
  ausencia de lógica en todos los DTOs.
- `tests/architecture/test_one_class_per_file.py` mantiene la política ECM-54.
- Los contratos por slice viven en `tests/features/<feature>/.../test_*dto_contract.py`
  y comprueban campos, tipos, inmutabilidad, serialización y mapeo.
- Cada ticket de migración debe añadir pruebas de las reglas 1–6 y del contrato
  DTO de su slice, y eliminar los shims que deje de necesitar.
- El formato y el lint se configuran con Ruff en `pyproject.toml` y se ejecutan
  en CI; no se introduce `mypy`, `black` ni `flake8` como parte de este ADR.

## Mapa de migración: archivo viejo → archivo nuevo

Las rutas marcadas **(ECM-xx)** ya están materializadas en la rama de ese ticket;
las marcadas **propuesto** son destino de este ADR y se crean con contenido real
en su ticket correspondiente. Las rutas antiguas se conservan como shims hasta
la limpieza final.

### Kernel compartido

| Archivo viejo | Archivo nuevo | Ticket |
|---|---|---|
| `domain/model/bbox.py` | `src/vision_core/shared/domain/bbox.py` | ECM-60 |
| `domain/model/event.py` | `src/vision_core/shared/domain/event.py` | ECM-60 |
| `domain/model/event_type.py` | `src/vision_core/shared/domain/event_type.py` | ECM-60 |
| `domain/model/polygon.py` | `src/vision_core/shared/domain/polygon.py` | ECM-60 |
| `domain/types.py` | shim temporal; `Frame`/`Embedding` se ubican en el slice que los use o en `shared/domain/types.py` solo si varios slices los usan | propuesto |
| `domain/attendance.py` | `src/vision_core/features/reid/domain/entities/session_attendance.py` | propuesto |
| `domain/model/__init__.py`, `domain/ports/__init__.py` | `__init__.py` de los paquetes nuevos | ECM-60 |

### Video

| Archivo viejo | Archivo nuevo | Ticket |
|---|---|---|
| `domain/ports/video_source.py` | `src/vision_core/features/video/domain/ports/video_source.py` | propuesto |
| `infrastructure/video/rtsp_video_source.py` | `src/vision_core/features/video/infrastructure/adapters/rtsp_video_source.py` | propuesto |
| `infrastructure/video/file_video_source.py` | `src/vision_core/features/video/infrastructure/adapters/file_video_source.py` | propuesto |
| `infrastructure/video/latest_frame_source.py` | `src/vision_core/features/video/infrastructure/adapters/latest_frame_source.py` | propuesto |
| `infrastructure/video/frame_validation.py` | `src/vision_core/features/video/infrastructure/adapters/frame_validation.py` | propuesto |
| `infrastructure/video/capture_reference.py` | `scripts/capture_reference.py` (herramienta de calibración, no feature) | propuesto |
| — | `src/vision_core/features/video/infrastructure/dependencies.py` (`build_video`) | propuesto |

### Detección

| Archivo viejo | Archivo nuevo | Ticket |
|---|---|---|
| `domain/model/detection.py` | `src/vision_core/features/detection/domain/entities/detection.py` | ECM-61 |
| `domain/ports/detector_manager.py` | `src/vision_core/features/detection/domain/ports/detector_manager.py` | ECM-61 |
| `infrastructure/detection/yolo_detector_manager.py` | `src/vision_core/features/detection/infrastructure/adapters/yolo_detector_manager.py` | ECM-61 |
| `infrastructure/detection/track.py` | `src/vision_core/features/detection/infrastructure/adapters/track.py` | ECM-61 |
| `infrastructure/detection/iou.py` | `src/vision_core/features/detection/infrastructure/adapters/iou.py` | ECM-61 |
| `infrastructure/detection/motion_tracker.py` | `src/vision_core/features/detection/infrastructure/adapters/motion_tracker.py` | ECM-61 |
| `infrastructure/detection/README.md` | `src/vision_core/features/detection/README.md` | ECM-61 |
| — | `application/dto/request/request_detector.py` (`RequestDetector`) | ECM-61 |
| — | `application/dto/response/response_detector.py` (`ResponseDetector`) | ECM-61 |
| — | `application/use_cases/detect_persons.py` (`DetectPersons`) | ECM-61 |
| — | `application/mappers/detection_mapper.py` | ECM-61 |
| — | `src/vision_core/features/detection/infrastructure/dependencies.py` (`build_detection`) | ECM-61 |

### ReID

| Archivo viejo | Archivo nuevo | Ticket |
|---|---|---|
| `domain/ports/reid_memory.py` | `src/vision_core/features/reid/domain/ports/reid_memory.py` | propuesto |
| `infrastructure/reid/memory_reid.py` | `src/vision_core/features/reid/infrastructure/adapters/memory_reid.py` | propuesto |
| `infrastructure/reid/embedder.py` | `src/vision_core/features/reid/infrastructure/adapters/embedder.py` | propuesto |
| `infrastructure/reid/embedding_extractor.py` | se elimina: shim deprecado ya cubierto por ECM-53 | propuesto |
| `infrastructure/reid/README.md` | `src/vision_core/features/reid/README.md` | propuesto |
| — | `src/vision_core/features/reid/infrastructure/dependencies.py` (`build_reid`) | propuesto |

### Puerta y zonas

| Archivo viejo | Archivo nuevo | Ticket |
|---|---|---|
| `domain/ports/door_analytics.py` | `src/vision_core/features/door/domain/ports/door_analytics.py` | ECM-64 |
| `infrastructure/door/zone_observation.py` | `src/vision_core/features/door/domain/entities/zone_observation.py` | ECM-64 |
| `infrastructure/door/polygon_door_analytics.py` | `src/vision_core/features/door/infrastructure/adapters/polygon_door_analytics.py` | ECM-64 |
| `infrastructure/door/uncalibrated_analytics.py` | `src/vision_core/features/door/infrastructure/adapters/uncalibrated_analytics.py` | ECM-64 |
| `infrastructure/door/zone_config.py` | `src/vision_core/features/door/infrastructure/config/zone_config.py` | ECM-64 |
| `infrastructure/door/zone_loader.py` | `src/vision_core/features/door/infrastructure/config/zone_loader.py` | ECM-64 |
| `infrastructure/door/geometry.py` | `src/vision_core/features/door/infrastructure/geometry.py` | ECM-64 |
| `infrastructure/door/polygon_validation.py` | `src/vision_core/features/door/infrastructure/polygon_validation.py` | ECM-64 |
| `infrastructure/door/check_zones.py` | `scripts/check_zones.py` (herramienta de calibración) | ECM-64 |
| — | `application/dto/request/request_get_history.py`, `request_update.py` | ECM-64 |
| — | `application/dto/response/response_get_history.py`, `response_update.py` | ECM-64 |
| — | `application/use_cases/get_history.py`, `update_zone.py` | ECM-64 |
| — | `application/mappers/door_mapper.py` | ECM-64 |
| — | `src/vision_core/features/door/infrastructure/dependencies.py` (`build_door`) | ECM-64 |

### Monitor

| Archivo viejo | Archivo nuevo | Ticket |
|---|---|---|
| `infrastructure/monitor/state.py` | `src/vision_core/features/monitor/infrastructure/state.py` | ECM-65 |
| `infrastructure/monitor/renderer.py` | `src/vision_core/features/monitor/infrastructure/renderer.py` | ECM-65 |
| `infrastructure/monitor/http_server.py` | `src/vision_core/features/monitor/infrastructure/http/handler.py` y `http/server.py` | ECM-65 |
| `infrastructure/monitor/server.py` | `src/vision_core/features/monitor/infrastructure/http/server.py` (shim temporal durante ECM-65) | ECM-65 |
| `infrastructure/monitor/__main__.py` | `main.py` (entrypoint raíz; banderas CLI en el composition root) | propuesto |
| `infrastructure/monitor/index.html` | `src/vision_core/features/monitor/infrastructure/http/index.html` (recurso estático) | propuesto |
| — | `application/dto/request/request_frame.py`, `request_snapshot.py` | ECM-65 |
| — | `application/dto/response/response_frame.py`, `response_snapshot.py` | ECM-65 |
| — | `application/use_cases/get_frame.py`, `get_snapshot.py`, `publish_monitor_state.py` | ECM-65 |
| — | `application/mappers/monitor_mapper.py` | ECM-65 |
| — | `src/vision_core/features/monitor/infrastructure/dependencies.py` (`build_monitor`) | ECM-65 |

### Pipeline y composición

| Archivo viejo | Archivo nuevo | Ticket |
|---|---|---|
| `application/vision_core_app.py` | `src/vision_core/features/pipeline/application/use_cases/run_pipeline.py` (`RunPipeline`) | propuesto |
| `application/event_serializer.py` | `src/vision_core/features/pipeline/application/mappers/event_serializer.py` | propuesto |
| `application/README.md` | `src/vision_core/features/pipeline/README.md` | propuesto |
| `domain/model/resolved_track.py` | `src/vision_core/features/pipeline/domain/entities/resolved_track.py` | propuesto |
| `composition.py` | se disuelve en `main.py` y los `dependencies.py` de cada feature; shim temporal | propuesto |
| `main.py` | `main.py` (permanece en la raíz como composition root) | ECM-58 |
| `scripts/pipeline_tools/` | se mantiene en `scripts/` como decoradores de validación/benchmark | sin cambio |

### Configuración y pruebas

| Archivo viejo | Archivo nuevo | Ticket |
|---|---|---|
| Variables de `.env.example` repartidas en adaptadores | `src/vision_core/settings.py`; cada adaptador recibe su configuración por parámetro | propuesto |
| `config/zones.example.json`, `config/frigate.*.yml` | permanecen en `config/` (datos estáticos de ejemplo, nunca dentro de un feature) | sin cambio |
| `tests/application/test_vision_core_app.py` | `tests/features/pipeline/test_run_pipeline.py` | propuesto |
| `tests/application/test_event_serializer.py` | `tests/features/pipeline/test_event_serializer.py` | propuesto |
| `tests/domain/test_event.py`, `tests/test_event.py` | `tests/shared/domain/test_event.py` (se consolida duplicado) | ECM-60 |
| `tests/domain/test_attendance.py` | `tests/features/reid/test_session_attendance.py` | propuesto |
| `tests/infrastructure/detection/*` | `tests/features/detection/*` | ECM-61 |
| `tests/infrastructure/door/*` | `tests/features/door/*` | ECM-64 |
| `tests/infrastructure/monitor/*` | `tests/features/monitor/*` | ECM-65 |
| `tests/fakes/*` | `tests/fakes/*` (se mantienen: sirven a varios slices) | sin cambio |

## Trazabilidad de tickets

Este ADR es la referencia canónica de ubicación y límites para los tickets
**ECM-14 a ECM-24** y para todos los tickets del sprint 4. Cada ticket de esa
serie referencia esta decisión al entregar o migrar su código: sus artefactos
deben aparecer en el mapa anterior y cumplir las reglas de dependencia.

| Ticket | Entrega original | Sección de este ADR que lo rige | Slice destino |
|---|---|---|---|
| ECM-14 | Prerrequisito histórico no registrado en el historial disponible | Decisión / Reglas de dependencia | — |
| ECM-15 | Carga de YOLOv8n | Mapa → Detección | `features/detection` |
| ECM-16 | Filtro de clase COCO 0 | Mapa → Detección | `features/detection` |
| ECM-17 | Integración del tracker | Mapa → Detección | `features/detection` |
| ECM-18 | Benchmark de FPS | Mapa → Pipeline y composición | `scripts/` |
| ECM-19 | Extractor de embeddings | Mapa → ReID | `features/reid` |
| ECM-20 | Buffer con TTL de 60 s | Mapa → ReID | `features/reid` |
| ECM-21 | Similitud coseno | Mapa → ReID | `features/reid` |
| ECM-22 | Tests con embeddings | Mapa → ReID / pruebas | `tests/features/reid/` |
| ECM-23 | Definición de polígonos | Mapa → Puerta y zonas | `features/door` |
| ECM-24 | Point in polygon | Mapa → Puerta y zonas | `features/door` |

Los tickets ECM-60, ECM-61, ECM-64 y ECM-65 implementan los primeros slices de
este ADR; ECM-58 (este documento) los precede como decisión arquitectónica.
