# Glosario

Términos usados en código, eventos y runbooks. Cuando un término tenga un
significado distinto en el código, prevalece el código enlazado.

| Término | Significado |
|---|---|
| **Frame** | Una imagen capturada del stream. La captura conserva solo la más reciente y descarta la anterior; el monitor usa un buffer de 1 frame. |
| **bbox** | Caja delimitadora de una detección, normalmente `(x1, y1, x2, y2)` en píxeles del frame. El centro del bbox se envía a analítica de puerta. |
| **Detección** | Salida del detector YOLOv8n para la clase persona (`0`) con confianza configurada (por defecto `0.5`). Ver [detection](../src/vision_core/features/detection/README.md). |
| **Track** | Trayectoria local de una persona entre frames, mantenida por el tracker por IoU/velocidad. No es una identidad durable. |
| **`track_id`** | Identificador local del track. El tracker asigna IDs crecientes y no los reutiliza tras pérdidas; no debe usarse como identidad de persona ni persistirse como tal. |
| **`person_id`** | Identidad resuelta por ReID a partir del embedding. Es local al despliegue y al modelo; no es el nombre de una persona real. |
| **ReID** | *Re-identification*: asociar una detección con una identidad ya vista mediante similitud de embeddings. Umbral por defecto `0.85`. |
| **Embedding** | Vector normalizado extraído del crop de una persona (`mobilenet_v3_small` o `resnet50`). No mezclar embeddings de modelos distintos en una misma sesión. |
| **Galería** | Conjunto limitado de embeddings recientes por identidad (por defecto 8). |
| **TTL** | Tiempo de vida. En ReID limita cuánto se conserva una identidad ausente; en persistencia define cuánto se retiene cada tipo de dato (`0` = sin borrado por tiempo). |
| **Zona** | Polígono calibrado sobre el frame con un nombre y un rol (`exterior`, `interior`, `fuera`). Configurado en `config/zones.json` con `version: "1.0"`. |
| **Polígono** | Lista de puntos que delimita una zona. Debe tener al menos 3 puntos y coincidir con el `frame_size` capturado. |
| **Observación de zona** | Registro de que una persona estuvo en una zona en un instante. No es todavía un evento. |
| **Confirmación de zona** | Número de observaciones consecutivas requeridas para aceptar el cambio de zona (por defecto 3). |
| **Cruce** | Transición confirmada de una zona a otra. La transición relevante es `exterior → interior` (entrada) y `interior → exterior` (salida). Interior tiene prioridad en solapamientos. |
| **Evento** | Resultado de un cruce: `PERSON_ENTERED`, `PERSON_EXITED` o `FALSE_ALARM`. Es la unidad publicada al monitor, persistida y contabilizada en métricas. |
| **`FALSE_ALARM`** | Evento de `exterior → fuera`, incluso tras una salida previa. La región dibujada como "puerta" no restringe por sí sola los eventos. |
| **`event_id`** | Clave de idempotencia del evento. Evita contar dos veces un reintento (`UNIQUE` + `INSERT OR IGNORE`). |
| **`schema_version`** | Versión del contrato del evento (`1.0.0`). Cambia solo con un contrato nuevo y versionado. |
| **`session_id`** | Identificador de una ejecución del pipeline. Agrupa tracks, eventos y métricas en persistencia. |
| **`camera_id`** | Identificador estable de la cámara (`VISION_CORE_CAMERA_ID`). Hoy se usa en logs y en la generación de `event_id`; no hay agregación multi-cámara. |
| **Pipeline** | Orquestación `video → detección/tracking → embedding/ReID → puerta → evento → monitor`. Implementada en `RunPipeline`. Ver [flujo de datos](diagrams.md#flujo-de-datos). |
| **Render** | Producción de JPEG para el monitor. Puede desactivarse con `VISION_CORE_RENDER_ENABLED=0` o `--no-render`; en ese caso no se publican frames. |
| **Backpressure** | Política de descartar el frame antiguo cuando el consumidor no puede seguir el ritmo. Evita crecer la cola, pero reduce frames procesados. |
| **fail-open** | Con `VISION_CORE_DB_FAIL_OPEN=1`, un fallo de SQLite no detiene el video: el sistema sigue en memoria y `health()` informa del error. |
| **Retención** | Borrado periódico en segundo plano de eventos, observaciones, tracks, identidades, sesiones y métricas según sus TTL. |
| **`/health`** | Liveness: el proceso HTTP está vivo. |
| **`/ready`** | Readiness: configuración, modelo, fuente de video y disco. Devuelve `503` si falla un chequeo. |
| **`/metrics`** | Telemetría JSON (contadores, gauges e histogramas) del estado del monitor. |
| **DTO** | Objeto inmutable de transporte entre capas o features. No contiene lógica de negocio ni depende de `numpy`, `cv2` o `torch`. |
| **Puerto / adaptador** | Contrato abstracto en `domain/` y su implementación concreta en `infrastructure/`. `main.py` inyecta el adaptador. |
| **Frigate / go2rtc** | Servicio externo que entrega video RTSP a Vision Core. Vision Core hace su propia detección; Frigate no produce los eventos de negocio. |
| **RTSP** | Protocolo de stream. En el stack se usa TCP por defecto para reducir inestabilidad. Nunca pegues una URL con credenciales en logs o incidencias. |

Relacionado: [runbooks](runbooks/README.md), [observabilidad](observability.md),
[persistencia](persistence.md) y [ADR 0002](adr/0002-persistence-and-retention.md).
