# Vision Core

## Quickstart

```bash
git clone https://github.com/ECOSUR-TEAM/Vision-Core
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
main.py           entrypoint
tests/            un espejo de domain/ y application/
```

Regla: nada en `infrastructure/` importa de otra carpeta de `infrastructure/`.
Todo pasa por los ports en `domain/ports/`.

El orquestador (`application/vision_core_app.py`) mantiene el mapeo
`track_id local -> person_id` y, cuando `DetectorManager.pop_lost_track_ids()`
reporta que un track expiró, llama `ReIDMemory.mark_lost(...)` con su último
embedding. Sin esto, el TTL/similitud coseno de ReIDMemory nunca se dispara
en el pipeline real — ver `infrastructure/detection/README.md`.

## Módulos y dueños (Sprint 1)

| Carpeta | Port | Epic | Dueño(s) |
|---|---|---|---|
| `infrastructure/detection/` | `DetectorManager` | VC-DETECT | Carlos, Ameth |
| `infrastructure/reid/` | `ReIDMemory` | VC-REID | Briyan |
| `infrastructure/door/` | `DoorAnalytics` | VC-DOORLOGIC | Melissa |
| `application/vision_core_app.py` | — | VC-APP | Fabricio |

Cada quien trabaja solo en su carpeta → branch `feature/<módulo>` → PR revisado
por alguien que no sea el dueño.

## Embedder de ReID

`infrastructure/reid/embedder.py` → `TorchvisionEmbeddingExtractor`
(ResNet50 o MobileNetV3-Small de torchvision, sin repos externos ni pesos
aparte). Es el único embedder soportado; no se usa OSNet/torchreid.

Cada módulo documenta su propio README corto dentro de su carpeta al cerrarlo.
