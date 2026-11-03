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

## Validación de la ingesta (sin navegador)

El diagnóstico consulta el códec, formato comprimido, resolución y FPS declarados
con `ffprobe` (instalar FFmpeg en el equipo que ejecuta la prueba). Luego consume
frames con OpenCV/FFmpeg, exige H×W×3, `uint8` y resolución constante. El decoder
se configura para entregar BGR: el orden de canales no puede deducirse solo de los
valores de un ndarray. El formato `pix_fmt` de ffprobe corresponde al stream, no
al ndarray decodificado.

```bash
export VISION_CORE_RTSP_URL='rtsp://IP_FRIGATE:8554/NOMBRE_STREAM'
export VISION_CORE_RECONNECT_ATTEMPTS=5
export VISION_CORE_RECONNECT_DELAY_SECONDS=2
export VISION_CORE_TIMEOUT_MS=5000
python -m infrastructure.video.check_stream --frames 300 --transport tcp
```

El comando imprime JSON con apertura, duración media/p95/máxima de lectura,
intervalo entre frames, FPS efectivos de consumo y reconexiones. Los FPS incluyen
las pausas y, si se habilita, el procesamiento. No son necesariamente los FPS de
captura. La latencia cámara→detector queda como `null`: requiere timestamps de
captura y relojes sincronizados, o una prueba visual con reloj. No se confunde
el tiempo bloqueado en `read()` con latencia de extremo a extremo.

`--transport tcp` fuerza TCP tanto en ffprobe como en OpenCV; puede repetirse con
`--transport udp`. Una lectura exitosa verifica recepción con el transporte
solicitado; no se presenta como una inspección de paquetes. Un ffprobe ausente o
fallido deja estado `incomplete` y salida 1, aunque los frames sean válidos.

Para probar inferencia real, añade `--detector`. Actualmente
`YoloDetectorManager.process()` lanza `NotImplementedError`; por tanto, esa prueba
fallará hasta completar VC-DETECT. Sin esa opción, el informe indica
`detector_status: not_tested`. Las pruebas automatizadas comprueban el contrato
con un detector simulado, no certifican inferencia YOLO.

### Interrupción temporal real

En un entorno de pruebas, ejecuta el diagnóstico con suficientes frames
(`--frames 3000`) y desconecta temporalmente el stream de prueba en Frigate.
Restáuralo antes de agotar los reintentos. Comprueba que se reciben frames otra vez,
que `reconnections` aumenta y observa el máximo de lectura. Repite dejando la
fuente desconectada para comprobar salida 1 y `ConnectionError`. El tiempo total
incluye los timeouts por intento además de las pausas. Usa un stream de pruebas
para no interrumpir otras grabaciones.

Pruebas sin cámara: `python -m pytest -q`. Cubren formatos inválidos, cambio de
resolución, caída temporal, indisponibilidad persistente, consumo por el contrato
del detector y liberación ante errores. Códec real, FPS reales, latencia y
recuperación física siguen pendientes hasta disponer de Frigate.
