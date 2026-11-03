# Monitor en vivo de Vision Core

El monitor ejecuta el pipeline real de Vision Core y publica una interfaz web
local en **http://127.0.0.1:8080**. Frigate sigue proporcionando el video; las cajas,
IDs, embeddings, zonas y eventos proceden de Vision Core.

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

- Video con cajas, confianza de detección, ID corto de persona, track local y
  polígonos. El punto dentro de la caja indica la posición usada para las zonas.
- Lista de personas visibles y zona observada. El ID completo está en JSON y en
  el título del ID de la lista; el ID corto se usa para facilitar la lectura.
- FPS del pipeline y tiempo de detección, embeddings/ReID y zonas. No son medidas
  de latencia desde la cámara. La interfaz consulta resultados aproximadamente
  cada 100 ms, por lo que su refresco puede ser menor que los FPS de análisis.
- Entradas/salidas acumuladas durante esta ejecución y los últimos 100 eventos.
  Los contadores no son un aforo: la escena puede comenzar con personas dentro.
- Estados de inicio, video sin actualizar, error y desconexión. Tras cinco segundos
  sin resultados nuevos, el panel deja de presentar las personas como actuales.

Los IDs distinguen personas durante la sesión; no son reconocimiento facial ni
identidades nominales. ReID intenta recuperar IDs perdidos mediante similitud de
embeddings, con el TTL existente de 60 segundos desde que el tracker declara la
pérdida. No garantiza continuidad ante oclusiones, cruces o cambios de apariencia.

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

El complemento `docker-compose.monitor.yml` cambia el comando de `vision-core`
y publica su puerto 8080 en loopback. Para webcam con zonas de demostración:

```bash
VISION_CORE_MONITOR_DEMO_ZONES=1 docker compose \
  -f docker-compose.yml -f docker-compose.webcam.yml -f docker-compose.monitor.yml \
  up -d --build
```

Para un Frigate remoto y zonas calibradas, configura `.env` con su URL accesible
**desde Docker** y `VISION_CORE_ZONES_FILE=config/zones.json`:

```bash
docker compose -f docker-compose.yml -f docker-compose.monitor.yml up -d --build
```

No añadas el complemento de webcam al conectarte al Frigate remoto: sobrescribe
la URL RTSP con el servicio local. Para detener el conjunto usa los mismos `-f`
y `down`. Detén el monitor Python antes de iniciar el de Docker si ambos usan 8080.
Los pesos YOLO y torchvision deben estar disponibles; el primer inicio puede
requerir descarga. La construcción de la imagen no se verificó en esta sesión.

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

Un hilo posee la captura RTSP y conserva únicamente el frame más reciente. Si
la inferencia tarda, reemplaza los frames intermedios en lugar de crear una cola
creciente. El contador de descartados incluye ese reemplazo, no pérdida de red.
Las reconexiones siguen la política del adaptador RTSP existente.

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
