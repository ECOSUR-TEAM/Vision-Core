# Runbook 03: Modelo no encontrado o error de inferencia

**Síntoma:** `/ready` devuelve `503` con `model=false`, el pipeline se detiene
al cargar pesos o aparecen códigos `MODEL_UNAVAILABLE`, `REID_MODEL_INVALID`,
`REID_MODEL_UNAVAILABLE` o `PIPELINE_FAILED`.

## Verificación rápida

```bash
curl http://127.0.0.1:8080/ready
docker compose --profile camera logs --tail 80 vision-core
docker compose --profile camera exec vision-core ls -la /model-cache /model-cache/torch
```

En Python local, con `.env` exportado:

```bash
python -c "import torch, torchvision; print(torch.__version__, torchvision.__version__, torch.cuda.is_available())"
```

Filtra los logs por `error_code` y `level=ERROR`. El código `message` es seguro
para pegar en un ticket; las rutas y URLs se redactan.

## Acción

1. **Detección:** por defecto se usa `yolov8n.pt`. Los pesos `*.pt` no están
   versionados. Comprueba que el archivo existe y es legible en el entorno
   correcto: en Compose, `/model-cache/torch` (volumen `vision-model-cache`);
   en local, la ruta de `VISION_CORE_MODEL_PATH`. El primer arranque necesita
   Internet para descargarlos.
2. **ReID:** `VISION_CORE_EMBEDDING_MODEL` admite `mobilenet_v3_small` y
   `resnet50`. Si se cambia el modelo a mitad de una sesión, no mezcles
   embeddings: reinicia la sesión y, si procede, limpia la galería/identidades
   según la política de retención.
3. **Dispositivo:** `VISION_CORE_DETECTION_DEVICE=cpu` y
   `VISION_CORE_EMBEDDING_DEVICE=cpu` son la configuración probada. Una CUDA
   explícita (`cuda`, `cuda:0`) falla si no hay GPU; verifica versiones
   compatibles de torch/torchvision antes de cambiarla.
4. **Permisos y caché:** si el archivo existe pero no carga, revisa permisos y
   caché de Torch. No borres `/model-cache` sin confirmar que hay conexión
   para volver a descargar.
5. **Reconstruir:** si los pesos se copiaban al construir la imagen, aplica el
   cambio y reconstruye:

   ```bash
   docker compose --profile camera up --build
   ```

6. **Reintentar:** reinicia el consumidor y comprueba `/ready`:

   ```bash
   docker compose --profile camera restart vision-core
   curl http://127.0.0.1:8080/ready
   ```

## Señal de éxito

- `/ready` devuelve `200` con `model=true`.
- `vision_core_frames_processed_total` crece y no aparecen nuevos errores de
  modelo. Si hay inferencia pero no eventos, pasa al
  [runbook de eventos](06-no-se-generan-eventos.md).

## Escalado

Si el error persiste con pesos locales y dispositivo CPU, registra versión de
torch/torchvision, nombre del modelo y `error_code`, y escala al responsable
del modelo. No sustituyas pesos por otros de arquitectura distinta sin
actualizar la configuración y la documentación. Guías relacionadas:
[observabilidad](../observability.md) y [validación](../validation.md).

## Evidencia ECM-104

Simulacro `weights_missing`: detección en 0.50 s y recuperación en 4.00 s,
dentro del objetivo de 4.00 s. `/ready` pasó a `503` antes de abrir el stream y
el error se reportó con `MODEL_UNAVAILABLE` / `CONFIGURATION_INVALID`. Evidencia
completa en [resultados de simulacros](../../reports/incident-drills.md).
