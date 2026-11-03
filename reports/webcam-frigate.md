# Prueba webcam → Frigate → Vision Core

Fecha: 2026-11-03. Linux, webcam del host `/dev/video0`, Frigate Docker
`0.17.2-3d4dd3a`, OpenCV 5.0.0. Configuración:
`config/frigate.webcam.example.yml` y `docker-compose.webcam.yml`.

Comando ejecutado con el Python del entorno local:

```bash
VISION_CORE_RTSP_URL=rtsp://127.0.0.1:28554/entrada python -m infrastructure.video.check_stream --frames 100 --transport tcp
```

Resultado: código 0, `status=ok`.

| Comprobación | Resultado |
|---|---|
| Frigate | Contenedor saludable; API de versión accesible |
| ffprobe | H.264, yuv420p, 640 × 480, 15/1 FPS |
| Lectura OpenCV | 100 frames BGR uint8 |
| Reconexiones | 0 |
| Apertura | 3327 ms |
| Consumo | 17.24 frames/s (incluye frames almacenados en buffer) |
| Lectura media / p95 | 58.00 / 70.82 ms |
| Suite existente | 163 passed, 4 skipped |
| Compose | Configuración combinada válida |

La prueba no ejecutó detector, ReID ni zonas, ni midió latencia extremo a extremo.
No se certificó visualmente la interfaz en navegador ni se construyó la imagen
Docker de Vision Core. La lectura se hizo con Python en el host contra el Frigate
real en Docker. La webcam no sustituye la calibración ni la evaluación de la sala.
No se guardaron imágenes de la webcam en el repositorio.
