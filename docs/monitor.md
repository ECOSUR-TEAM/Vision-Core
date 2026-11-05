# Monitor en vivo de Vision Core

El monitor ejecuta el pipeline real de Vision Core y publica una interfaz web
local en **http://127.0.0.1:8080**. Frigate sigue proporcionando el video; las cajas,
IDs, embeddings, zonas y eventos proceden de Vision Core.

## Arranque principal

```bash
docker compose up
```

El monitor y Frigate se inician juntos. No hace falta iniciar Python ni ejecutar
comandos adicionales de red. [Arranque, parada y preparación inicial](startup.md).
Los comandos Python que siguen son alternativas para desarrollo; no se ejecutan
junto con el monitor Docker en el mismo puerto.

## Iniciar con la webcam

Desde la raíz, con Frigate local iniciado según [la guía de Frigate](frigate.md):

```bash
source venv/bin/activate  # O .venv/bin/activate, según tu instalación.
set -a
source .env
set +a
python -m infrastructure.monitor --demo-zones --port 8080
```

`.env` debe contener `VISION_CORE_RTSP_URL=rtsp://127.0.0.1:28554/entrada`.
Abre http://127.0.0.1:8080. El comando permanece activo; Ctrl+C detiene el monitor.
No hace falta ejecutar `main.py` a la vez: el monitor ya construye el pipeline.
La detección de Frigate puede permanecer desactivada.

El modo `--demo-zones` usa `config/zones.example.json`, con resolución 640 × 480.
La mitad izquierda es exterior y la derecha interior. Mueve el centro de tu
cuerpo entre ambas mitades para observar entradas/salidas. La posición usada es
el centro de la caja, no los pies. Se necesitan tres observaciones consecutivas
por zona de forma predeterminada. Cerca del borde, el ruido de la caja puede
producir transiciones: estos eventos no representan una puerta real calibrada.

## Qué muestra

- Video como elemento principal, con recuadros y etiquetas «Persona 1», «Persona 2».
  El número se conserva si ReID recupera a la misma persona después de perderla.
- Cantidad de personas visibles y una lista sencilla. Con zonas calibradas también
  indica si están dentro, fuera o fuera de las zonas marcadas.
- Avisos claros cuando la imagen se detiene o se pierde la conexión. Si el navegador
  no recibe una imagen nueva en 2,5 segundos, deja de mostrar el conteo como actual.

El panel no muestra FPS, porcentajes, identificadores técnicos, tiempos ni tablas
 de eventos. Estos datos siguen disponibles en `/api/state`. En modo demostración
se ocultan los polígonos y aparece «Calibración pendiente»; los eventos de ejemplo
siguen calculándose internamente pero no se presentan como movimientos reales.

Los IDs distinguen personas durante la sesión; no son reconocimiento facial ni
identidades nominales. ReID intenta recuperar IDs perdidos mediante similitud de
embeddings, durante esta ejecución de forma predeterminada
(`VISION_CORE_REID_TTL_SECONDS=0`). No garantiza continuidad ante oclusiones, cruces o cambios de apariencia.

## Zonas reales y Frigate remoto

Cambia `VISION_CORE_RTSP_URL` al restream remoto, exporta `.env` y calibra las zonas
con [la guía de validación](validation.md). Inicia sin `--demo-zones`:

```bash
python -m infrastructure.monitor --zones config/zones.json --port 8080
```

Mantén `VISION_CORE_MONITOR_DEMO_ZONES=0` (predeterminado). Si vale `1`, activa las
zonas de ejemplo incluso cuando se proporciona `--zones`. La resolución real debe
coincidir con la calibración. Un error detiene la analítica y permanece visible
en el panel; corrige la configuración y reinicia el monitor.

## Docker

El archivo principal `docker-compose.yml` ejecuta el monitor y sus dependencias.
Para dejarlo en segundo plano: `docker compose up -d`; para detenerlo:
`docker compose down`. Al actualizar código: `docker compose up --build`.

Después de calibrar, configura `VISION_CORE_MONITOR_UNCALIBRATED=0` y la ruta
`VISION_CORE_ZONES_FILE` en `.env`. Hasta entonces el monitor acepta la resolución
nativa sin generar cruces de sala. La imagen utiliza CPU y un volumen de caché
para pesos. Los reinicios del proceso borran la memoria temporal de identidades.

## Implementación y acceso

`VisionCoreApp` dispone de un observador opcional `on_frame(frame, tracks, ms)`,
ejecutado una vez al terminar cada frame, incluso si no hay detecciones.
El monitor consume los mismos IDs y eventos que el pipeline normal. No realiza
una inferencia adicional por navegador. La API expone:

| Ruta | Respuesta |
|---|---|
| `/` | Panel claro, sin recursos web externos |
| `/api/state` | Estado, personas, métricas y eventos recientes JSON |
| `/api/frame` | Último JPEG anotado; 503 mientras no haya frames |
| `/api/frame?after=N` | Espera hasta 1 s por una imagen posterior a N; 204 si aún no llega. Incluye `X-Frame-Sequence`. |

Un hilo posee la captura RTSP y conserva únicamente el frame más reciente. Si
la inferencia tarda, reemplaza los frames intermedios en lugar de crear una cola
creciente. El contador de descartados incluye ese reemplazo, no pérdida de red.
Las reconexiones siguen la política del adaptador RTSP existente.

El decodificador usa un solo hilo (`VISION_CORE_DECODER_THREADS=1`) para evitar
la cola de salida que puede introducir la decodificación H.264 multihilo. Se puede
usar `0` para volver a selección automática, por ejemplo para evaluar rendimiento
con resoluciones mayores. Esta opción requiere OpenCV con `CAP_PROP_N_THREADS`.
Referencia: [propiedades oficiales de OpenCV](https://docs.opencv.org/4.13.0/d4/d15/group__videoio__flags__base.html).

La imagen se solicita inmediatamente después de mostrar la anterior; si no hay
una nueva, el servidor espera y la entrega al publicarse. No hay una pausa fija
entre imágenes ni una cola por navegador. La consulta de personas/estado ocurre
cada 500 ms por separado y no bloquea el video. Si el servidor se reinicia, el
cliente reinicia también su número de secuencia.

No se promete latencia cero. El sensor, codificador de Frigate, red, inferencia y
pantalla aún añaden tiempo. Para medir el retraso absoluto, apunta la cámara a un
reloj con milisegundos y compara ese reloj con la imagen del panel en una misma
captura. Los FPS y la edad de publicación del JPEG no miden ese retraso total.

El monitor conserva imágenes y eventos solo en memoria. Está pensado para pruebas
locales, sin autenticación. El bind predeterminado es `127.0.0.1`; `--host 0.0.0.0`
permite acceso desde otros equipos de una red de confianza mediante la IP de la
laptop. El Compose publica solo en loopback, aun cuando el servidor dentro del
contenedor escucha en `0.0.0.0`.

## Verificación realizada

2026-11-03: Frigate real de la webcam, YOLOv8n y MobileNet V3 Small en CPU. Se
observaron detecciones de persona, IDs y eventos de ambas direcciones; una muestra
registró unos 15 FPS. No es una medición de precisión ni capacidad garantizada.

Chromium automatizado comprobó frames actualizados, datos reales, diseño claro,
escritorio de 1440 px y móvil simulado de 390 px sin desbordamiento horizontal,
estados de datos antiguos, desconexión y recuperación, sin errores JavaScript.
No se probó en teléfono físico. Suite Python: 168 pasaron, 4 omitidos.


2026-11-04: comparación simultánea de la decodificación automática y de un hilo
sobre el mismo restream de webcam. Se emparejaron 159 frames por SHA-256 de sus
píxeles BGR. La versión automática entregó esas mismas imágenes una mediana de
996 ms más tarde (mínimo 986 ms, máximo 1804 ms). Es una comparación entre
configuraciones; no mide latencia absoluta sensor→pantalla. Suite: 171 pasaron,
4 omitidos. Se mantienen las zonas de ejemplo sin calibración real.

La interfaz simplificada se verificó en Firefox con video real: 30 imágenes nuevas
recibidas en 2 segundos, sin errores JavaScript. Se comprobaron anchos de 390,
768 y 1440 px sin desbordamiento, recuperación tras interrumpir el video y
actualización de imágenes independiente de una consulta de datos retrasada.
La prueba de 15 imágenes/s verifica fluidez, no latencia absoluta.


## Cámara Ethernet sin calibración

Para usar la resolución nativa de una cámara nueva, sin polígonos de ejemplo:

```bash
python -m infrastructure.monitor --uncalibrated --port 8080
```

Este modo admite 1280 × 800 de la Vivotek FD8134 y otras resoluciones. Detecta y
recuerda personas pero no genera entradas/salidas hasta que haya zonas reales.
El texto «Calibración pendiente» sigue visible. Al volver a ver a alguien, la
etiqueta se conserva si el tracker o la memoria recuperan su identidad.
Consulta [la memoria de sesión](../infrastructure/reid/README.md).
