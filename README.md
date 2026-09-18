# Vision Core

## Quickstart

```bash
git clone <repo>
cd vision-core
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```

## Arquitectura

```
domain/           entidades + ports (contratos), sin dependencias externas
application/      VisionCoreApp: orquesta el pipeline usando solo los ports
infrastructure/   implementaciones concretas (una carpeta por módulo/dueño)
tests/            un espejo de domain/ y application/
```

Regla: nada en `infrastructure/` importa de otra carpeta de `infrastructure/`.
Todo pasa por los ports en `domain/ports/`.

## Módulos y dueños (Sprint 1)

| Carpeta | Port | Epic | Dueño(s) |
|---|---|---|---|
| `infrastructure/detection/` | `DetectorManager` | VC-DETECT | Carlos, Ameth |
| `infrastructure/reid/` | `ReIDMemory` | VC-REID | Briyan |
| `infrastructure/door/` | `DoorAnalytics` | VC-DOORLOGIC | Melissa |
| `application/vision_core_app.py` | — | VC-APP | Fabricio |

Cada quien trabaja solo en su carpeta → branch `feature/<módulo>` → PR revisado
por alguien que no sea el dueño.

## Pendiente por módulo (`TODO` en el código)

- **DetectorManager** (`infrastructure/detection/yolo_detector_manager.py`): cargar YOLOv8, filtrar
  clase "person" (confidence > 0.5), tracking con ByteTrack/Norfair.
- **ReIDMemory** (`infrastructure/reid/memory_reid.py`): embeddings (ResNet/MobileNet), buffer TTL 60s,
  similitud coseno > 0.85.
- **DoorAnalytics** (`infrastructure/door/polygon_door_analytics.py`): point-in-polygon, historial de
  posiciones, clasificación ENTRÓ/SALIÓ/FALSA_ALARMA.

Cada módulo documenta su propio README corto dentro de su carpeta al cerrarlo.
