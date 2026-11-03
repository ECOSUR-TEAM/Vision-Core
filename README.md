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
export VISION_CORE_OPEN_TIMEOUT_MS=5000
export VISION_CORE_READ_TIMEOUT_MS=5000
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

Para probar inferencia real, añade `--detector`. `YoloDetectorManager` carga los pesos locales `yolov8n.pt` y ejecuta inferencia. Sin esa opción, el informe indica
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


## Frames de Frigate → detecciones de personas

El pipeline pasa cada frame al detector existente, que carga YOLO una sola vez.
La entrada es BGR `uint8`, H×W×3; Ultralytics realiza su propio preprocesamiento.
La inferencia recibe `classes=[0]` y `conf=0.5`. El adaptador vuelve a filtrar
estrictamente `confidence > 0.5`: una detección con confianza exactamente 0.5
se descarta. El umbral está definido en `CONFIDENCE_THRESHOLD`.

Cada resultado se convierte en `Detection` con `BBox` xyxy en píxeles del frame
original, confianza, clase 0 y el ID del tracker existente. Se recortan coordenadas
fuera del frame y se descartan cajas no finitas, invertidas o sin área; no se
normalizan las coordenadas al intervalo 0–1 ni se reescalan por segunda vez.
Referencia: [contrato de predicción de Ultralytics](https://docs.ultralytics.com/modes/predict/).

Para probar Frigate y YOLO sin ejecutar ReID:

```bash
python -m infrastructure.video.check_stream --frames 300 --transport tcp --detector
```

Las pruebas automatizadas cubren carga única, opciones de inferencia, clase,
umbral estricto, formato del frame y cajas inválidas/fuera de límites.
La prueba de video real requiere `DETECTION_TEST_VIDEO` y `DETECTION_TEST_MODEL`.

## Calibrar puerta y zonas con la cámara

No hay una imagen real de la sala incluida. `config/zones.example.json` contiene
coordenadas sintéticas y no constituye una calibración válida de la cámara.

1. Con `VISION_CORE_RTSP_URL` configurada, captura sin navegador:
   `python -m infrastructure.video.capture_reference referencia.png`.
2. Abre el PNG a resolución original en un editor que muestre coordenadas del
   cursor. Copia `config/zones.example.json` a `config/zones.json`. Escribe en
   `frame_size` el ancho y alto mostrados por la captura.
3. Marca los vértices de `door` (puerta), `exterior` e `interior` en orden alrededor
   de cada contorno. No repitas el primer punto al final. El origen es la esquina
   superior izquierda; x crece a la derecha e y hacia abajo. Los puntos deben
   quedar dentro de la imagen y los contornos no deben cruzarse consigo mismos.
4. Revisa la superposición:
   `python -m infrastructure.door.check_zones referencia.png config/zones.json zonas.png`.
   Exterior: azul; interior: verde; puerta: rojo. Los vértices están numerados.
5. Configura `VISION_CORE_ZONES_FILE=config/zones.json` en el entorno o `.env`.
   `main.py` exige esta configuración y verifica la resolución durante la lectura;
   cambiar resolución, encuadre o posición de cámara requiere recalibrar.

Los bordes y vértices pertenecen al polígono. Si interior y exterior comparten
un borde o se solapan, interior tiene prioridad; evita solapamientos de área no
intencionales. Se prueban puntos dentro, fuera, en cada borde y vértice, contornos
cóncavos, orientación inversa y configuraciones inválidas.

La puerta queda configurada y dibujada como región de referencia. Los eventos
actuales siguen usando las transiciones exterior/interior del centro del bbox;
no se exige cruzar el polígono de puerta para emitirlos. Esa regla corresponde a
la analítica de trayectorias y debe acordarse antes de modificar los eventos.
No confundas estas zonas del centro de la persona con polígonos medidos en el suelo.

## Eventos de zonas y ruido

`DoorAnalytics.update(person_id, position)` confirma una zona después de **3
observaciones consecutivas de esa persona**. Esto también se aplica a su zona
inicial: no se emite un cruce sin un origen confirmado. Se configura desde
`VISION_CORE_ZONE_CONFIRMATION_FRAMES` (entero positivo; `1` habilita transiciones
inmediatas para pruebas o comparación). Las pruebas anteriores de transiciones
usan explícitamente ese modo; las nuevas pruebas de ruido usan el valor 3.

| Transición confirmada | Evento |
|---|---|
| exterior → interior | `PERSON_ENTERED` |
| interior → exterior | `PERSON_EXITED` |
| exterior → fuera | `FALSE_ALARM` |

Las demás transiciones y la permanencia en una zona no producen eventos.
`FALSE_ALARM` conserva el significado del contrato actual: cualquier transición
exterior→fuera confirmada, incluso después de una salida previa.

Cada evento contiene el `person_id`, timestamp Unix en segundos del instante de
confirmación y metadata con origen, destino, posición y número de observaciones
requeridas. El timestamp es de procesamiento, no el de captura de la cámara.

`PolygonDoorAnalytics.get_history(person_id)` devuelve una instantánea inmutable
con posición, zona observada y timestamp, incluidas observaciones aún no confirmadas.
Conserva las últimas 300 por persona (`history_limit` configurable en constructor).
El estado es independiente por persona; no hay persistencia en disco ni expiración
automática de personas en esta analítica.

Si la detección vuelve a la zona confirmada o cambia de candidata, se reinicia la
confirmación. Esto evita eventos por oscilaciones breves del centro del bbox sobre
el borde y permite nuevos cruces reales posteriores. No elimina ruido que dure
3 observaciones o más. Las ausencias sin llamadas a `update()` no avanzan ni
reinician el contador; el umbral no equivale a una duración fija en segundos.

Pruebas: `python -m pytest tests/infrastructure/door -q`. Cubren los tres eventos,
identidades independientes, timestamps, historial acotado, puntos no finitos,
ruido alrededor del borde y entrada/salida/entrada sin bloquear cruces legítimos.
La efectividad del umbral en la sala debe validarse con el video real.
