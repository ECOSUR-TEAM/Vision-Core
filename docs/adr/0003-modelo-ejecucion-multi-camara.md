# ADR 0003: Modelo de ejecución multi-cámara y estrategia de ReID compartido

| Campo | Valor |
|---|---|
| Estado | **Propuesto** |
| Fecha | 2026-11-18 |
| Tipo | Arquitectura / Decisión condicional |
| Prioridad | Alta |
| Ticket | ECM-89 |
| Etiquetas | `architecture`, `adr`, `multi-camera`, `reid`, `concurrency`, `gpu`, `backpressure` |
| Dependencias | ADR 0001; ADR 0002 (persistencia y retención); profiling single-camera; `LatestFrameBuffer` / `RendererThread` |
| Impacto | Bloquea cualquier implementación multi-cámara hasta confirmación de requisitos |

## Estado

**Propuesto.** Este documento no autoriza implementación ni modificación de código.
Registra una decisión **condicional**: la arquitectura objetivo solo se activa si
Negocio confirma por escrito los requisitos de hardware, número de cámaras y
necesidad real de identidad *cross-camera*. Mientras tanto, el sistema permanece
en su modelo actual de un proceso por cámara con ReID local.

Cualquier cambio de este ADR debe hacerse mediante un ADR nuevo que lo sustituya,
según la convención de `docs/adr/README.md`.

## Contexto

### Estado actual del sistema

El despliegue operativo es **un proceso, una cámara, una identidad local**:

| Componente | Situación actual | Consecuencia |
|---|---|---|
| Proceso | `main.py` (composition root) → `RunPipeline` (`features/pipeline/application/use_cases/run_pipeline.py`), un `VideoSource` | Un único flujo de video por proceso; no hay namespace de cámara. |
| Captura | `LatestFrameSource` posee un hilo lector y un buffer de tamaño 1 con descarte de lo viejo | La captura nunca espera a inferencia; los frames intermedios se pierden deliberadamente. |
| Inferencia | YOLOv8n para detección y MobileNet V3 Small para embeddings, secuenciales, envueltos en `torch.inference_mode()` | Un solo hilo de IA; sin batching real (los flags `VISION_CORE_EMBEDDING_BATCH_SIZE` y `VISION_CORE_EMBEDDING_STRIDE` son preparatorios). |
| ReID | `InMemoryReID` por proceso (`VISION_CORE_REID_TTL_SECONDS=0`, sesión) y `PersistingReIDMemory` / `PersistenceService` sobre SQLite (ADR 0002), con `VISION_CORE_IDENTITY_TTL_SECONDS=86400` (1 día) | Las identidades y embeddings sobreviven al reinicio; dos cámaras siguen sin compartir `person_id` sin un store o servicio compartido. |
| Analítica | `DoorAnalytics` + zonas + `SessionAttendance`, con eventos persistidos por `PersistenceService` (ADR 0002) | Los eventos sobreviven al reinicio, pero siguen asociados a una sola cámara. |
| Render/JPEG | `RendererThread` en hilo propio consume `LatestFrameBuffer` de tamaño 1; `RenderJob.capture` copia el frame y congela metadatos | El render ya está desacoplado del hilo de inferencia; se puede desactivar con `VISION_CORE_RENDER_ENABLED=0`. |
| Observabilidad | `MonitorState` en memoria, servidor HTTP local y `FrameProfiler` opcional (opt-in) con `perf_counter()` para `decode`, `detection`, `embedding`, `reid_tracking`, `analytics` y `frame_total`, con p50/p95/FPS en `profiling_results.json` | Tenemos baseline single-camera, pero aún no métricas con etiqueta `camera_id`, ni agregación multi-cámara. |
| Hardware observado | Ejecución CPU con yolov8n + MobileNet V3 Small a 640 × 480, del orden de 15 FPS según `docs/monitor.md` | No existe medición de GPU compartida ni de contención entre cámaras. |

El punto de partida es, por tanto, **frescura antes que exhaustividad**: se descartan
frames para proteger latencia, y se sacrifica continuidad entre cámaras para
evitar acoplamiento. Esa elección fue correcta para una cámara; deja de serlo si
aparece el requisito de seguir a la misma persona entre dos streams.

### Requisitos hipotéticos a validar

Los valores siguientes son **hipótesis de trabajo**, no requisitos aprobados.
Deben confirmarse antes de cualquier implementación:

| Requisito | Hipótesis a validar | Por qué condiciona la decisión |
|---|---|---|
| Latencia objetivo | p95 de captura→JPEG ≤ 500 ms; p99 ≤ 1 s; frescura visible ≤ 1 s | Define si el batching es admisible: una ventana de batch de 10–20 ms consume una fracción del presupuesto, pero una cola de 100 ms lo invalida. |
| Throughput | 15–30 FPS por cámara, 2–4 cámaras iniciales, 8 como horizonte | Define el número de streams a multiplexar y si un solo proceso puede sostenerlos. |
| Identidad *cross-camera* | Hipótesis **sí**: una persona debe conservar `person_id` al pasar de la cámara A a la B | Es el único requisito que justifica un almacén compartido; si es falso, la Opción A gana por defecto. |
| Presupuesto de hardware | 1 nodo, 4–8 CPU, 16 GB RAM, GPU opcional con hasta 8 GB VRAM, red local 1 GbE | Sin GPU o con menos de ~4 GB libres, la duplicación de modelos de la Opción A es inviable y la Opción B pierde sentido. |
| Retención y privacidad | Embeddings como dato personal: TTL de 1 día ya aceptado en ADR 0002 (`VISION_CORE_IDENTITY_TTL_SECONDS=86400`); borrado individual gobernado por retención/API de persistencia | Determina si el almacén compartido necesita tumbstones, auditoría y cifrado, no solo TTL. |
| Disponibilidad | Degradación aceptable: perder ReID *cross-camera* es tolerable; perder detección local no | Permite diseñar un modo degradado sin shared store en lugar de un failover costoso. |
| Persistencia | SQLite durable ya aceptada en ADR 0002, con `PersistingReIDMemory` / `PersistenceService` y degradación fail-open | Un ReID compartido debe reutilizar esa base y sus repository ports, no depender de replay ni introducir otro store sin justificación. |

## Opciones Consideradas

### Opción A — Un proceso por cámara

Cada cámara ejecuta el pipeline completo: captura, detección, embedding, ReID
local, analítica de zonas y render, con su propio puerto de monitor y su propio
`profiling_results.json`.

**Pros**

- Aislamiento fuerte de fallos: un `SIGSEGV`, un `RuntimeError` de OpenCV o un
  desbordamiento de memoria en la cámara 2 no afecta a la 1.
- Propiedad de memoria explícita: `InMemoryReID`, `MonitorState`, zonas y
  `SessionAttendance` son locales; no hay locks distribuidos ni consenso.
- Backpressure trivial y ya resuelto: buffer de tamaño 1 por cámara con drop-old;
  el productor nunca espera al renderer.
- Reinicio por cámara independiente con supervisor (systemd o restart policy de
  contenedor), sin coordinación entre procesos.
- Latencia mínima y predecible: una sola pasada forward por frame, sin espera de
  batch ni serialización IPC.
- El profiling actual es directamente comparable entre cámaras si se añade la
  etiqueta `camera_id` al archivo de salida.

**Contras**

- Duplicación de modelos: cada proceso carga YOLOv8n y MobileNet, más un
  contexto CUDA propio cuando hay GPU. El coste real no son los pesos (~decenas
  de MB), sino el contexto CUDA y los workspaces (~300–600 MB por proceso como
  estimación a medir). Con 4 cámaras, el factor de multiplicación es 4×.
- No existe identidad *cross-camera*: dos procesos generan UUID distintos para
  la misma persona. Requiere necesariamente un servicio externo si el requisito
  aparece.
- N puertos HTTP, N configuraciones, N superficies de observabilidad; la
  operación crece linealmente con el número de cámaras.
- Contención de CPU: varios decodificadores OpenCV + varias pasadas PyTorch
  compiten por núcleos y ancho de banda de memoria; en CPU el throughput total
  no escala linealmente con el número de procesos.
- Agregación posterior (si se quiere un panel único) exige un colector, que es
  precisamente el IPC que esta opción intentaba evitar.

### Opción B — Servicio de inferencia compartido con batching

Un único proceso posee los modelos y expone un endpoint de inferencia. Los
productores envían frames/crops y reciben detecciones y embeddings; el
scheduler agrupa varios crops en un batch.

**Pros**

- Una sola copia de los modelos y un solo contexto CUDA: el consumo de VRAM
  crece con el batch, no con el número de cámaras.
- Mejor utilización de GPU: las pasadas pequeñas (batch=1, como hoy) subutilizan
  los núcleos; un batch de 4–8 amortiza lanzamiento de kernels y transferencias.
- Punto natural para normalizar embeddings y aplicar una política de ReID
  global: el resolver ve todas las cámaras en el mismo lugar.
- Centraliza el profiling de inferencia: una sola serie temporal de
  `detection`/`embedding` con etiqueta por cámara.

**Contras**

- Latencia: el batching introduce espera de ventana (típicamente 5–20 ms) más
  ida y vuelta IPC. Con objetivo p95 ≤ 500 ms es asumible; con objetivo ≤ 100 ms
  no lo es. Además, el *tail* se degrada por head-of-line blocking: un crop
  grande retrasa a los demás del mismo batch.
- Cuello de botella único: el servicio es un SPOF y su cola es el punto donde se
  acumula la presión de todas las cámaras.
- IPC caro: un frame BGR 640 × 480 × 3 son ~0.9 MB sin comprimir; a 4 cámaras ×
  15 FPS son ~55 MB/s solo en frames, más copias de serialización. Enviar crops
  por broker agrava el problema.
- Complejidad de batching dinámico: padding, máscara, formas heterogéneas,
  temporizadores de flushing y priorización por cámara. Esto sí altera la
  arquitectura actual y queda fuera del alcance del ticket de optimización
  previo, que solo dejó flags.
- Consistencia de ReID: resolver identidades desde varias cámaras requiere
  serialización de escrituras o CAS; si no, dos cámaras pueden asignar UUID
  distintos a la misma persona en el mismo intervalo.
- Fallo parcial: si el servicio de inferencia cae, los workers siguen capturando
  pero no producen resultados; hay que transformar eso en un estado degradado
  explícito, no en un bucle silencioso.

### Opción C — Modelo híbrido

Captura, tracking local (IoU/moción), zonas, eventos y render se ejecutan en un
**worker por cámara**. La inferencia pesada (detección + embedding) se centraliza
en un servicio con batch pequeño. El ReID compartido vive en un servicio de
identidad con almacén propio.

**Pros**

- Equilibrio: el trabajo ligero y sensible a latencia (decodificar, dibujar,
  publicar JPEG, mantener tracks) se queda junto a la cámara; el trabajo caro
  y paralelizable se comparte.
- El worker puede seguir sirviendo el último JPEG conocido y marcar
  `status=degraded` si el servicio de inferencia falla: aislamiento de fallos
  sin duplicar modelos.
- Identidad *cross-camera* resuelta en un único lugar, con política de TTL,
  borrado y auditoría centralizada.
- El buffer de tamaño 1 y el renderer por cámara se reutilizan tal cual; el
  cambio está en la frontera entre worker e inference service.
- Permite escalar por escalones: 2 cámaras con batch=1 antes de activar batching.

**Contras**

- Dos saltos de red por frame (worker → inference → worker), más un tercero al
  servicio de identidad. El presupuesto de latencia debe repartirse
  explícitamente.
- Tres unidades desplegables con ciclos de vida independientes: más superficie
  de health checks, timeouts, reintentos y configuración.
- Modos de fallo compuestos: inference OK + store caído, store OK + inference
  lenta, worker vivo + stream muerto. Cada uno necesita un estado observable
  distinto.
- Requiere un protocolo de mensajes con `camera_id`, `sequence`, `capture_ts` y
  versión de zonas; hoy esos conceptos no cruzan ningún límite de proceso.
- Coste operativo superior al de A; solo se justifica si la identidad
  *cross-camera* es un requisito real.

### Por qué `threading` puro y `asyncio` puro no son viables

- **GIL**: el intérprete serializa bytecode Python. Aunque las kernels de
  PyTorch y parte de OpenCV liberan el GIL, la orquestación (`numpy`, control de
  tracks, mappers, serialización) no lo hace. Varios hilos de inferencia en un
  mismo proceso no producen paralelismo real de CPU y sí más contención.
- **Asyncio**: solo concurrentiza E/S. No acelera una pasada forward ni la
  decodificación; bloquear el event loop con un `model(...)` sincrónico congela
  todas las cámaras. Para usar `asyncio` haría falta un executor, que es exactamente
  el modelo de concurrencia que se descarta para inferencia.
- **Aislamiento**: un fallo nativo en un hilo mata el proceso completo; no hay
  reinicio por cámara.
- **GPU**: varios hilos pueden emitir kernels, pero compiten por el mismo
  contexto CUDA y por ancho de banda; no reduce VRAM y añade sincronización.
- **Límite correcto de los hilos**: el `RendererThread` actual es válido porque
  hace E/JPEG y producción de bytes, no inferencia; `cv2.imencode` libera el GIL.
  Es un caso de E/S, no un mecanismo de escalado de IA.

### Matriz comparativa

| Criterio | A: proceso por cámara | B: inferencia compartida | C: híbrido |
|---|---|---|---|
| Latencia p95 | **Mejor** (sin IPC ni batch) | Regular (ventana + RTT) | Aceptable (2 saltos, tracking local) |
| Throughput agregado | Limitado por CPU y duplicación | **Mejor** en GPU | Bueno si batch pequeño |
| VRAM / RAM | **Peor**: N copias | **Mejor**: 1 copia | Buena: 1 copia + workers ligeros |
| Aislamiento de fallos | **Mejor** | **Peor**: SPOF | Medio: degradación por capa |
| Identidad *cross-camera* | No | Sí, con CAS | **Sí**, con store dedicado |
| Complejidad operativa | Baja | Media-alta | **Alta** |
| Backpressure | Buffer 1 por cámara | Cola compartida, riesgo de head-of-line | Buffer 1 + cola acotada de inferencia |
| Adecuado si | No hay ReID compartido | Hay GPU y latencia holgada | Hay ReID compartido **y** presupuesto |

## Decisión

### Decisión recomendada (Go / No-Go)

**Ir por el modelo híbrido (Opción C) solo si Negocio confirma simultáneamente:**

1. que la identidad *cross-camera* es un requisito funcional verificable (caso de
   uso con cámara de entrada y cámara de salida);
2. que existen al menos 2 cámaras iniciales y un horizonte ≤ 8 por nodo;
3. que el presupuesto incluye un nodo con GPU compartida y ≥ 4 GB VRAM libres
   después de reservar sistema, **o** un presupuesto CPU explícito para al menos
   2 núcleos por cámara;
4. que el objetivo de latencia p95 ≤ 500 ms permite el RTT IPC y una ventana de
   batch ≤ 20 ms;
5. que existe una política aprobada de retención y borrado de embeddings.

**Si falta cualquiera de esas condiciones: NO IMPLEMENTAR.** Se mantiene la
Opción A (un proceso aislado por cámara) con ReID local, sin servicio de
inferencia compartido, sin broker y sin cambio en el contrato de identidad. Es
la decisión por defecto porque preserva el baseline medido y evita introducir
un SPOF sin beneficio demostrado.

**Bloqueo explícito:** la implementación real está bloqueada hasta que Negocio
confirme por escrito hardware, número de cámaras y requisito de identidad. Este
ADR no crea código, no añade dependencias y no modifica el pipeline actual.

### Puertas de validación (secuencia obligatoria)

| Puerta | Criterio de salida | Si falla |
|---|---|---|
| G0 — Baseline | `profiling_results.json` por cámara con p50/p95/FPS etiquetados por `camera_id` y al menos 30 s de medición | No escalar: no hay comparación "antes/después". |
| G1 — Requisitos | Confirmación formal de hardware, cámaras y ReID *cross-camera* | Mantener Opción A. |
| G2 — PoC 2 cámaras | Híbrido con batch=1: p95 dentro del objetivo y sin regresión >10 % frente a G0 | Mantener Opción A o revisar objetivo de latencia. |
| G3 — Batch | Solo si G2 pasa: activar batch pequeño y medir VRAM y p95 de cola | Desactivar batch; quedarse con inferencia compartida sin batching. |
| G4 — Identidad | Prueba A→B con borrado propagado en < 1 s | No activar ReID compartido; degradar a local. |

### Estrategia de ReID e identidad

| Dimensión | Memoria local por cámara (hoy) | Almacén / servicio compartido |
|---|---|---|
| Namespace | UUID por proceso; colisiones lógicas entre cámaras | `person_id` global con `camera_id` de última observación |
| Consulta | `resolve()` en memoria, sin red | Local write-through + fallback remoto con CAS |
| Latencia | Nanosegundos | 1–5 ms en Redis local; más si hay Vector DB remoto |
| Consistencia | Instantánea dentro del proceso | Eventual acotada (< 1 s) para búsqueda *cross-camera*; read-your-writes para la cámara de origen |
| Fallo | Pierde identidad al reiniciar | Degrada a IDs locales con flag `reid_degraded`; sin resurrección de borrados |
| Retención | TTL persistido de 1 día (ADR 0002); la memoria cálida de sesión usa `VISION_CORE_REID_TTL_SECONDS=0` | Reutilizar el TTL de 1 día y el borrado por `person_id`; tumbstones para borrado propagado |
| Privacidad | Borrado gobernado por retención/API de persistencia (ADR 0002), no reiniciar proceso | Borrado por `person_id` propagado a cachés; auditoría y cifrado |

**Modelo de consistencia elegido (si se activa C):** caché local por worker con
escritura en el store compartido (*write-through*). La cámara que resolvió una
identidad conserva autoridad sobre ella mientras la identidad siga vigente según el TTL de 1 día de ADR 0002; las demás
hacen búsqueda por similitud con lectura eventual. Para evitar que dos cámaras
creen UUID distintos para la misma persona, la asignación de un `person_id` nuevo
debe ser una operación atómica en el servicio (comparar-and-set sobre el
embedding canónico), no una decisión independiente por worker.

**Semántica de fallos:**

- Store caído: los workers siguen detectando y usando IDs locales, marcan el
  estado `reid_degraded` y dejan de intentar recuperaciones *cross-camera*; no
  se encolan reintentos indefinidos.
- Store recuperado: se sincroniza la versión más reciente; un tumbstone nunca se
  sobrescribe con un embedding antiguo (el borrado gana sobre la inserción).
- Inference caída: el worker publica el último JPEG con `status=degraded`; no
  inventa detecciones ni recicla tracks.

**Elección de tecnología:** para el horizonte de 2–8 cámaras y del orden de
miles de embeddings, primero debe evaluarse reutilizar los repository ports y la
base SQLite de ADR 0002. Solo si esa vía no cubre la búsqueda por similitud con
las garantías de TTL y borrado, un Redis local sería una opción intermedia y
mucho más simple que un Vector DB. Un Vector DB (HNSW/IVF) se justifica solo si
la galería supera ~10^5 vistas o se requiere búsqueda aproximada con filtros;
introducirlo antes añade un servicio más sin beneficio medible. Los embeddings
se tratan como dato personal: cifrado en tránsito y en reposo, TTL de 1 día
definido en ADR 0002, y borrado individual que propaga tumbstones a
todas las cachés de worker en menos de 1 s.

### Comunicación y backpressure

- **Regla invariante:** ninguna cola sin límite. El buffer de frame es de tamaño
  1 por cámara y aplica descarte de lo viejo; la cola de inferencia, si existe,
  está acotada a 1–2 elementos por cámara con la misma política. El productor
  nunca bloquea esperando espacio: sobreescribe y contabiliza `dropped_frames`.
- **Identificadores de mensaje:** `camera_id`, `sequence` monotónico,
  `capture_ts` y `zone_version`. El consumidor descarta mensajes con
  `sequence <= ultima_secuencia_procesada`, aunque lleguen desordenados.
- **En-proceso vs broker:** mientras haya un solo nodo, la comunicación debe ser
  en-proceso (como hoy) o, como mucho, memoria compartida local para los pixels
  más un mensaje pequeño de metadatos. Un broker (Kafka/RabbitMQ/Redis Streams)
  se introduce **solo** si aparece multi-nodo, durabilidad o replay.
- **Si se necesita IPC:** preferir Redis Streams con `MAXLEN ~ 2`, consumer group
  por worker y ACK tras publicar; es más simple que Kafka y encaja con el store
  de identidad. Kafka/RabbitMQ quedarían reservados a escenarios multi-nodo con
  auditoría de eventos, y su retención por tiempo entra en tensión con la
  política de frescura: un frame viejo es peor que un frame perdido.
- **No enviar frames crudos por el broker:** 0.9 MB por frame a 4 × 15 FPS son
  ~55 MB/s de copias. Compartir memoria para el array y enviar solo metadatos
  mantiene el coste proporcional al número de detecciones, no a los píxeles.
- **Señal de presión:** `dropped_frames`, profundidad de cola y espera de batch
  son métricas de primer nivel; si crecen de forma sostenida, la respuesta es
  reducir cámaras o resolución, nunca aumentar el tamaño de la cola.

### Ciclo de vida, salud y presupuesto de recursos

**Health checks por unidad desplegable:**

| Unidad | Liveness | Readiness | Métricas clave |
|---|---|---|---|
| Worker por cámara | `frame_age ≤ 2 s` y decoder sin error | Modelo remoto alcanzable y zonas cargadas | `fps`, `dropped_frames`, `processing_ms`, `render_age`, `camera_id` |
| Servicio de inferencia | Proceso vivo y contexto GPU sin pérdida | Cola y latencia de batch dentro de umbral | `queue_depth`, `batch_wait_p95`, `detection_p95`, `embedding_p95`, `vram_used` |
| Servicio de identidad | Store responde | TTL y borrado operativos | `reid_p95`, `store_errors`, `tombstones_applied`, `cache_size` |

El `FrameProfiler` actual se convierte en la fuente de p50/p95 por etapa; debe
añadir `camera_id` como dimensión y exportar las mismas etapas que hoy registra
en JSON, sin cambiar el significado de `frame_total`. El panel actual
(`/api/v1/state`, con `/api/state` como alias deprecado) sigue siendo por cámara;
la agregación es responsabilidad de un colector nuevo, no del worker.

**Reinicios y aislamiento:** cada worker se reinicia de forma independiente con
un supervisor, con backoff y un límite de intentos para evitar bucles. El
reinicio de un worker pierde su caché ReID local y debe anunciarse como tal; el
reinicio del servicio de inferencia no debe reiniciar a todos los workers, sino
marcarlos `degraded` hasta que vuelva a estar listo. El store de identidad, si se
adopta, es el único componente con estado que sobrevive a reinicios.

**Apagado controlado:** `SIGTERM` → dejar de capturar → drenar la cola acotada
con un plazo de 1–2 s → publicar el último JPEG → cerrar conexiones del store →
salir con código 0. Después de un plazo máximo (10 s) el supervisor fuerza la
salida. Los frames que no alcanzaron a procesarse se contabilizan como
descartados, no se encolan para el próximo arranque.

**Presupuesto máximo de cámaras por nodo:** debe calcularse con la fórmula

`N_max = floor(min(VRAM_libre / VRAM_por_camara, RAM_libre / RSS_por_worker,
CPU_utiles / CPU_por_camara))`

 aplicando un margen de seguridad del 20–30 %. Como heurística provisional a
medir en G0/G2: un worker con modelo propio puede requerir ~1 GB de RAM y
~300–600 MB de contexto CUDA; un worker sin modelos (Opción C) puede situarse en
~150–300 MB de RAM. En CPU, cada cámara consume del orden de 1.5–2 núcleos
equivalentes con 640 × 480 a 15 FPS. Con 8 GB VRAM y 4–8 núcleos, la Opción A
quedaría limitada a ~2–4 cámaras, mientras que la Opción C podría alojar más
workers porque el modelo es único. Estos números son **estimaciones de
planificación**, no mediciones reales: G0 debe sustituirlos por datos antes de
fijar el límite operativo.

## Consecuencias

### Positivas

- La decisión es explícitamente condicional: evita pagar el coste de un servicio
  compartido mientras no haya un caso de uso que lo justifique.
- El modelo por defecto (Opción A) conserva el aislamiento, el drop-old y el
  profiling single-camera que ya están implementados y medidos.
- Si se activa la Opción C, el tracking, las zonas y el renderer no cambian: el
  cambio se concentra en la frontera IPC y en el resolver de identidad.
- La política de colas acotadas y descarte de lo viejo queda como invariante
  arquitectónico, no como detalle de implementación.
- La estrategia de ReID define desde el principio borrado, degradación y
  consistencia, evitando un rediseño posterior del contrato de `person_id`.

### Negativas y costes

- La Opción A multiplica memoria y no resuelve identidad *cross-camera*: es una
  decisión deliberada de no escalar, no una solución definitiva.
- La Opción C añade dos servicios, un protocolo y tres modos de fallo nuevos;
  el equipo debe aceptar esa carga operativa antes de activarla.
- El batching mejora throughput pero consume presupuesto de latencia y puede
  empeorar el p95 por head-of-line blocking; por eso queda detrás de la Puerta G3.
- Un store compartido convierte un problema local (reiniciar el proceso) en un
  problema de gobernanza de datos: TTL, cifrado, auditoría y borrado son ahora
  requisitos funcionales.

### Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Batching activado sin baseline | Puerta G0: sin p50/p95 etiquetados por cámara, no se escala. |
| Cola compartida creciendo y añadiendo latencia | Colas de 1–2, drop-old y alarma sobre `dropped_frames`; prohibido aumentar `maxsize` como solución. |
| Dos cámaras asignan distinto `person_id` a la misma persona | Asignación atómica (CAS) en el servicio de identidad; G4. |
| Borrado de identidad no propagado | Tumbstones con TTL y verificación en G4; el borrado gana sobre cualquier inserción tardía. |
| Caída del inference service interpretada como "sin personas" | Estado `degraded` explícito y último JPEG con marca de edad, nunca detecciones falsas. |
| Hilos/asyncio introducidos para "paralelizar" inferencia | Regla: hilos solo para E/S y render; inferencia sigue secuencial por worker. |
| Broker introducido "por si acaso" | Solo multi-nodo o auditoría; en un nodo, memoria compartida + metadatos. |
| Límite de cámaras estimado sin medir | Sustituir heurísticas por datos de G0/G2 antes de fijar `N_max`. |

### Dependencias y prerrequisitos

1. **Observabilidad:** añadir `camera_id` a `profiling_results.json` y exponer
   los mismos p50/p95 por etapa en un endpoint de métricas. Sin esto no hay
   comparación antes/después ni criterio objetivo para las puertas.
2. **Profiling single-camera:** el baseline actual (`decode`, `detection`,
   `embedding`, `reid_tracking`, `analytics`, `frame_total`) debe quedar
   congelado como referencia de regresión antes de cualquier cambio de modelo de
   ejecución.
3. **Política de retención:** ya aprobada en ADR 0002 (identidades, embeddings y
   personas 1 día; tracks 1 día; eventos 30 días) y configurable con
   `VISION_CORE_IDENTITY_TTL_SECONDS=86400`. Cualquier almacén compartido debe
   reutilizarla; no se introduce un TTL alternativo sin una decisión explícita.
4. **Invariantes ya implementados:** `LatestFrameBuffer` de tamaño 1,
   `RendererThread` con `stop`/`join` y `torch.inference_mode()` en detección y
   embedding se conservan en cualquiera de las opciones.
5. **ADR 0001:** el modelo sigue siendo Vertical Slice; un servicio de
   inferencia y otro de identidad serían features nuevos con sus propios ports y
   DTOs inmutables, sin importar infraestructura ajena.

### Verificación futura (cuando se levante el bloqueo)

- Reproducir el caso A→B con la misma persona y verificar un único `person_id`.
- Ejecutar el borrado de esa identidad y comprobar que ningún worker la
  devuelve después del plazo acordado (según TTL de 1 día de ADR 0002 o borrado
  inmediato propagado).
- Matar el servicio de inferencia y verificar que los workers siguen publicando
  JPEG con `status=degraded`, sin excepciones en cadena.
- Overflow controlado: inyectar frames más rápido de lo que consume el renderer
  y confirmar que `dropped_frames` crece pero la memoria se mantiene plana.
- Apagado con `SIGTERM` y comprobación de que no quedan hilos ni procesos
  colgados después del plazo de gracia.
- Comparar p50/p95 de G0 contra G2/G3 con la misma cámara y resolución; si el
  p95 empeora más del 10 %, la decisión revierte a la Opción A.
