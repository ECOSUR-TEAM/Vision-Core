# Requisitos y problemas conocidos

## Requisitos de ejecución

- Equipo con Python/PyTorch/torchvision compatibles, CPU y memoria suficientes para
  cargar YOLOv8n y el extractor. No hay mínimo RAM/CPU ni FPS garantizados medidos
  en la sala. Considera además el coste independiente de Frigate si comparte host.
- Espacio para entorno Python, pesos y videos. El tamaño depende de las versiones,
  duración y resolución; CUDA instala dependencias adicionales.
- GPU opcional: NVIDIA con driver, PyTorch CUDA y acceso al dispositivo para el
  extractor CUDA. CPU está probada; no había CUDA disponible en la evaluación local.
- OpenCV con backend FFmpeg y soporte del códec real; FFmpeg/ffprobe para diagnóstico.
- Red entre Vision Core y Frigate y entre Frigate y cámara; el ejemplo usa RTSP TCP
  en 8554. Resolución/encuadre estables para conservar la calibración.

La evidencia disponible y sus condiciones están en
[el informe de evaluación](../reports/room-evaluation.md). No extrapolar una demo
sintética corta a aforo máximo ni a latencia real.

## Frigate local con webcam

Consulta [la guía de prueba y migración](frigate.md). La webcam debe aparecer
como dispositivo V4L2 en el host Linux y estar disponible para Docker. En una VM
hay que pasar el dispositivo al host que ejecuta Docker.

- Si un puerto está ocupado, revisa `ss -ltn`: el ejemplo publica 15000 (web) y
  28554 (RTSP), ambos en loopback; ajusta Compose y la URL de `.env` juntos.
- Si la cámara está ocupada, cierra el proceso que la usa antes de iniciar Frigate.
- Si no hay frames, comprueba dispositivo, formatos y FPS con FFmpeg; edita
  `config/frigate-local/config.yml` y reinicia el servicio local.
- Para liberar la cámara usa `docker compose -f docker-compose.yml -f docker-compose.webcam.yml down`.
- La configuración local persiste fuera de Git; el video temporal está en tmpfs.

## Diagnóstico

| Síntoma | Comprobación / acción |
|---|---|
| Falta `VISION_CORE_RTSP_URL` o `VISION_CORE_ZONES_FILE` | Copiar y editar `.env.example`; exportar `.env` en Bash. Python no lo carga solo. |
| No conecta o agota reintentos | Revisar host Frigate, puerto 8554, nombre go2rtc, autenticación y accesibilidad desde el contenedor. |
| Funciona web antigua, falla RTSP | Confirmar ruta/códec del modelo Vivotek en Frigate; no usar URL HTTP de administración como video. |
| `ffprobe` ausente / diagnóstico incompleto | Instalar FFmpeg en el host; el Dockerfile actual no incluye su ejecutable. |
| Timeout o no permite salida BGR | Confirmar build OpenCV con FFmpeg y timeouts; probar el códec real. Aumentar timeouts solo si la red lo justifica. |
| Error de resolución | Capturar referencia nueva y recalibrar; no reescalar polígonos a ciegas. |
| Falla carga de pesos | Verificar `yolov8n.pt`, permisos, caché Torch y red para primera descarga. |
| Error torch/torchvision o CUDA | Instalar versiones compatibles usando el selector oficial de PyTorch; probar CPU y `pip check`. |
| IDs cambian en cruces u oclusiones | Revisar cajas/IoU, duración de ausencia y embeddings; el tracker no usa apariencia. |
| No hay eventos | Confirmar zonas del centro del bbox y al menos 3 observaciones consecutivas en origen y destino. |
| Eventos repetidos cerca del borde | Revisar calibración y ruido; aumentar confirmación solo tras medir el retraso adicional. |
| Archivo de salida ya existe | Elegir nombre nuevo; los comandos de captura/demo/registro evitan sobrescribir. |

## Monitor web

La analítica en vivo se ve en http://127.0.0.1:8080 al ejecutar
`python -m infrastructure.monitor --demo-zones`. Consulta [la guía](monitor.md).
Si el panel muestra error, revisa stream, pesos y resolución de zonas, y reinicia
el monitor. Si 8080 está ocupado, usa `--port 8081`. El monitor no muestra mensajes
nativos de error ni URLs RTSP en HTTP para evitar exponer credenciales.

## Límites funcionales

El tracker usa velocidad e IoU; no es ByteTrack completo. Tolera 30 frames
procesados ausentes; la red caída no incrementa ese contador. ReID usa embeddings
ImageNet y umbral fijo, sin entrenamiento específico de personas. No mezclar
embeddings de modelos distintos durante una sesión.

La región puerta se configura y dibuja, pero no restringe los eventos: se usan
transiciones exterior/interior/fuera. Interior tiene prioridad en solapamientos.
FALSE_ALARM significa exterior→fuera, incluso tras una salida previa. El historial
se acota por persona, pero no se eliminan automáticamente todas las personas antiguas
de la analítica. Estado e identidades viven en memoria y se pierden al reiniciar.

`main.py` no persiste eventos ni tiene supervisor. Un fallo no recuperable detiene
el proceso tras intentar cerrar el video. El runner JSONL es la salida estructurada
para pruebas. Los logs nativos pueden contener URLs; revisar antes de compartir.

Los archivos se reproducen a velocidad de procesamiento y el TTL avanza con reloj
real, no con el tiempo del video. EOF y algunos errores de archivo pueden parecerse;
revisar frames obtenidos. El tiempo de `read()` o de inferencia no mide latencia
cámara→evento: hacen falta timestamps de captura o una prueba con reloj visible.

No se probaron instalación limpia ni construcción Docker en esta tarea documental.
Las dependencias no están fijadas; registrar versiones junto a los resultados.
