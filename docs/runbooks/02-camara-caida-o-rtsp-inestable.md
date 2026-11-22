# Runbook 02: Cámara caída o RTSP inestable

**Síntoma:** `/ready` devuelve `503` con `video_source=false`, aumentan las
reconexiones, el monitor se queda sin frames o aparece un error de fuente de
video.

## Verificación rápida

```bash
curl http://127.0.0.1:8080/ready
docker compose --profile camera ps -a
docker compose --profile camera logs --tail 80 camera-bridge
docker compose --profile camera logs --tail 80 frigate
docker compose --profile camera logs --tail 80 vision-core
docker compose --profile camera exec camera-bridge python /app/camera_bridge.py check
```

En `/metrics`, revisa `vision_core_reconnections_total` y
`vision_core_frames_processed_total`. En logs, filtra por `error_code` de la
familia `VIDEO_SOURCE_*` (catálogo en [errors.md](../errors.md)). No compartas
la URL RTSP.

Para probar el stream desde Python, con `.env` exportado:

```bash
python -m vision_core.scripts.check_stream --frames 100 --transport tcp
```

## Acción

1. **Físico:** confirmar alimentación, Ethernet y que la cámara responde en la
   red. Si DHCP cambió la IP, actualiza `FRIGATE_CAMERA_RTSP_URL` en `.env` y
   vuelve a `docker compose --profile camera up -d`.
2. **Puente:** si `camera-bridge` está `unhealthy`, comprobar la ruta
   `/live.sdp` del modelo Vivotek FD8134 y el host/puerto configurados. El
   puente solo reenvía TCP al destino configurado. Guía específica:
   [ethernet-camera.md](../ethernet-camera.md).
3. **Frigate:** abrir http://127.0.0.1:15000 y confirmar que el stream entra.
   Si la webcam funciona pero RTSP no, revisar la configuración de restream en
   [frigate.md](../frigate.md).
4. **Transporte:** el stack usa RTSP/TCP por defecto. Probar `tcp` primero;
   cambiar a `udp` solo con evidencia de que el problema es TCP. Ajusta
   `VISION_CORE_RTSP_TRANSPORT` y `OPENCV_FFMPEG_CAPTURE_OPTIONS` juntos.
5. **Timeouts:** `VISION_CORE_OPEN_TIMEOUT_MS` y
   `VISION_CORE_READ_TIMEOUT_MS` valen `5000`. Aumentarlos solo si la red está
   realmente lenta; `VISION_CORE_RECONNECT_ATTEMPTS=5` y
   `VISION_CORE_RECONNECT_DELAY_SECONDS=2` controlan los reintentos.
6. **Reintento controlado:** tras corregir, reiniciar solo el consumidor:
   `docker compose --profile camera restart vision-core`. El reinicio pierde la
   memoria temporal de identidades; si hay base configurada, el histórico se
   conserva.

## Señal de éxito

- `/ready` vuelve a `200` y `vision_source=true`.
- `vision_core_frames_processed_total` crece y no aparecen nuevos
  `VIDEO_SOURCE_*` en los logs.
- El monitor vuelve a mostrar el stream con retraso aceptable. Si el problema
  es de fluidez, continúa con
  [05. FPS bajo o latencia alta](05-fps-bajo-o-latencia-alta.md).

## Escalado

Si el stream entra en Frigate pero Vision Core no lo lee, registra los
contadores y el `error_code`, y escala al responsable de red/cámara. No
desactives `restart: unless-stopped` ni aumentes reintentos de forma
permanente sin una causa documentada.
