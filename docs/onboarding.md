# Onboarding

Guía de primeros pasos. No repite el README: da el camino mínimo para arrancar,
entender el sistema y saber dónde buscar. El índice completo está en
[docs/README.md](README.md).

## 1. Requisitos

- Docker Engine con Compose; o Python 3.11 con FFmpeg, `libgl1` y `libglib2.0-0`.
- Git y acceso a GitHub/GHCR para la primera descarga de imágenes y pesos.
- Opcional: cámara RTSP (Vivotek FD8134) o webcam V4L2 en Linux. Sin cámara se
  puede trabajar con video sintético.

## 2. Instalación y arranque

### Opción A: Docker (recomendada)

```bash
docker compose up                    # video sintético, sin cámara
docker compose --profile camera up   # cámara Ethernet + Frigate
docker compose down                  # parar y retirar contenedores
```

Abre http://127.0.0.1:8080 para el monitor; con el perfil `camera`, Frigate está
en http://127.0.0.1:15000. `frigate-config` terminando con `Exited (0)` es
normal. La primera vez hay que copiar `.env.example` a `.env` y rellenar
`FRIGATE_CAMERA_RTSP_URL`; el detalle está en [startup.md](startup.md).

### Opción B: Python local

```bash
make setup
make test
make run
```

`make setup` crea `.venv`, instala dependencias CPU, copia `.env.example` a
`.env` si no existe y genera `dev-data/sample.avi` con sus zonas. `make run`
arranca el monitor con ese video sintético. **Python no carga `.env`
automáticamente**: para ejecutar `python main.py` hay que exportarlo antes:

```bash
set -a
source .env
set +a
python main.py
```

Más opciones (Dev Container, GPU, puertos) en [development.md](development.md).

## 3. Arquitectura en cinco minutos

Vision Core es una **vertical slice** organizada por Screaming Architecture:
`video`, `detection`, `reid`, `door`, `monitor` y `pipeline` dentro de
`src/vision_core/features/`. Cada feature tiene sus capas `domain/`,
`application/` e `infrastructure/`; se comunican mediante DTOs y puertos.
`main.py` en la raíz es el único composition root.

- Reglas de imports y DTOs: [architecture.md](architecture.md).
- Motivo de la decisión: [ADR 0001](adr/0001-screaming-architecture-vertical-slice.md).
- Vista visual: [diagramas Mermaid](diagrams.md), especialmente
  [contexto](diagrams.md#c4--contexto), [contenedores](diagrams.md#c4--contenedores),
  [componentes](diagrams.md#c4--componentes) y
  [flujo de datos](diagrams.md#flujo-de-datos).
- Componentes que aún viven en `src/vision_core/{application,domain,infrastructure}`
  están en migración; no son un segundo dominio global.

## 4. Comandos que usarás

| Comando | Para qué |
|---|---|
| `make setup` / `make test` | Preparar entorno / ejecutar pytest |
| `make lint` / `make format` / `make format-check` | Ruff |
| `make run` | Monitor local con video sintético |
| `make docker-build` | Construir imágenes del stack (`--profile camera`) |
| `docker compose up` / `down` | Stack sintético |
| `docker compose --profile camera up` | Stack con cámara y Frigate |
| `python -m vision_core.scripts.check_stream --frames 100 --transport tcp` | Probar RTSP |
| `python -m vision_core.scripts.validate_pipeline --zones config/zones.json --frames 3000 --output sala.jsonl` | Registro estructurado de prueba |
| `curl http://127.0.0.1:8080/health` y `/ready` | Comprobar proceso y dependencias |

La lista completa, con cobertura y mypy, está en
[README.md](../README.md#ejecutar-tests-localmente) y [testing.md](testing.md).

## 5. Primeros pasos

1. Arranca el stack sintético y confirma que el monitor muestra recuadros y
   conteo de personas. Los IDs son temporales, no nombres.
2. Ejecuta `make test` y `make lint` antes de tocar código.
3. Lee el [glosario](glossary.md) para no confundir `track_id` con `person_id`,
   ni un evento con una observación de zona.
4. Abre los [runbooks](runbooks/README.md) y saber dónde están `/ready`,
   `/metrics` y los logs antes de necesitarlos.
5. Si vas a calibrar, sigue [validation.md](validation.md#calibrar-puerta-y-zonas-con-la-cámara).
   No cambies resolución ni encuadre después de guardar los polígonos.
6. Toda entrega incluye documentación: consulta el
   [Definition of Done (ticket 40)](development.md#definition-of-done-ticket-40).

## 6. Si algo falla

Empieza por el [índice de runbooks](runbooks/README.md). Para diagnóstico
general, [operations.md](operations.md) tiene la tabla de síntomas y
[observability.md](observability.md) explica métricas y endpoints.
