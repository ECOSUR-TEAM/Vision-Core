# Diagramas (Mermaid)

Representación C4 en Mermaid (`flowchart`) para que los diagramas se versionen
como texto y se revisen en el mismo PR que el código. Se actualizan cuando
cambia el cableado en `main.py`, los adaptadores o los endpoints.

## C4 — Contexto

```mermaid
flowchart LR
    Operator["Operador / SRE"]
    Camera["Cámara IP o webcam"]
    Frigate["Frigate + go2rtc<br/>restream RTSP"]
    VC["Vision Core<br/>analítica de personas"]
    DB[("SQLite local<br/>eventos y métricas")]
    Monitor["Monitor web<br/>127.0.0.1:8080"]
    Obs["Logs JSON y /metrics"]

    Camera -->|"RTSP / V4L2"| Frigate
    Frigate -->|"RTSP TCP"| VC
    VC --> DB
    VC --> Monitor
    VC --> Obs
    Operator --> Monitor
    Operator --> Frigate
    Operator --> Obs
```

Vision Core no sustituye a Frigate: Frigate entrega video y Vision Core hace su
propia detección, ReID y generación de eventos. Fuera de alcance: sitio web
externo y sincronización entre nodos.

## C4 — Contenedores

```mermaid
flowchart TB
    subgraph Host["Nodo Docker"]
        Bridge["camera-bridge<br/>perfil camera"]
        Cfg["frigate-config<br/>copia config si falta"]
        FrigateC["frigate<br/>15000 / RTSP 28554"]
        VCC["vision-core<br/>main.py + monitor"]
        Synth["vision-core-synthetic<br/>video sintético"]
        Cache[("vision-model-cache")]
        Data[("vision-data<br/>SQLite")]
    end

    Camera["Cámara Ethernet"] --> Bridge
    Bridge --> FrigateC
    Cfg -->|"config completado"| FrigateC
    FrigateC -->|"rtsp://frigate:8554/entrada"| VCC
    MonitorN["Navegador :8080"]
    Synth -->|"dev-data/sample.avi"| MonitorN
    VCC --> MonitorN
    VCC --> Cache
    VCC --> Data
    Synth --> Cache
```

El stack por defecto levanta `vision-core-synthetic`; el perfil `camera`
levanta `camera-bridge`, `frigate-config`, `frigate` y `vision-core`. Ver
[startup.md](startup.md) y [docker-compose.yml](../docker-compose.yml).

## C4 — Componentes

```mermaid
flowchart TB
    Main["main.py<br/>composition root"]

    subgraph Features["src/vision_core/features"]
        Video["video<br/>RTSP / archivo / frame más reciente"]
        Detection["detection<br/>YOLO + tracking"]
        ReID["reid<br/>embeddings e identidad"]
        Door["door<br/>zonas y eventos"]
        Pipeline["pipeline<br/>RunPipeline"]
        Monitor["monitor<br/>estado, render y HTTP"]
    end

    subgraph Shared["shared / adaptadores"]
        Obs["observability<br/>health, logs, métricas"]
        Errors["errors<br/>taxonomía y envelope"]
        Persist["infrastructure/persistence<br/>SQLite y retención"]
        Settings["settings<br/>Settings.from_env()"]
    end

    Main --> Settings
    Main --> Video
    Main --> Detection
    Main --> ReID
    Main --> Door
    Main --> Persist
    Main --> Obs
    Main --> Monitor
    Pipeline --> Video
    Pipeline --> Detection
    Pipeline --> ReID
    Pipeline --> Door
    Pipeline --> Monitor
    Pipeline --> Obs
    Monitor --> Errors
```

Un feature nunca importa la infraestructura de otro: se comunica mediante
puertos y DTOs. Las reglas se comprueban en
`tests/architecture/test_import_rules.py`; el detalle está en
[architecture.md](architecture.md).

## Flujo de datos

```mermaid
flowchart LR
    Source["VideoSource<br/>RTSP o archivo"] --> Run["RunPipeline.run"]
    Run --> Res["Validar resolución<br/>contra frame_size"]
    Res --> Det["YOLOv8n persona<br/>conf 0.5"]
    Det --> Track["MotionTracker<br/>IoU 0.3, 30 frames"]
    Track --> Crop["Validar bbox<br/>y recortar"]
    Crop --> Emb["Embedding<br/>mobilenet_v3_small / resnet50"]
    Emb --> Identity["ReID<br/>umbral 0.85, TTL, galería 8"]
    Identity --> Analytics["PolygonDoorAnalytics<br/>centro del bbox + zonas"]
    Analytics --> Event["Evento<br/>ENTERED / EXITED / FALSE_ALARM<br/>schema 1.0.0"]
    Event --> State["MonitorState<br/>/api/v1/state"]
    Event --> Store[("SQLite<br/>eventos y métricas")]
    Event --> Obs["logs JSON y métricas"]
    Run --> FrameBuf["LatestFrameBuffer<br/>1 frame, descarta viejo"]
    FrameBuf --> Renderer["RendererThread"]
    Renderer --> FrameAPI["/api/v1/frame?after=N"]
    FrameAPI --> Browser["Monitor en el navegador"]
```

Código de referencia: `src/vision_core/features/pipeline/application/use_cases/run_pipeline.py`,
`src/vision_core/features/door/infrastructure/analytics/`,
`src/vision_core/features/monitor/infrastructure/` y
[main.py](../main.py). Con `VISION_CORE_MONITOR_UNCALIBRATED=1` se omite la
analítica de zonas y no se generan cruces; con
`VISION_CORE_RENDER_ENABLED=0` se omite la rama de render/JPEG.

## Cómo mantener estos diagramas

1. Cambias un adaptador o un endpoint → actualiza el diagrama afectado en el
   mismo PR.
2. Cambias una decisión estructural → añade o enmienda un ADR y enlázalo desde
   [el índice](adr/README.md).
3. Antes de mergear, verifica que los nombres de features, servicios y rutas
   HTTP siguen existiendo; los comandos están en
   [onboarding.md](onboarding.md#4-comandos-que-usarás).
