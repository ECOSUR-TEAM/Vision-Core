# Runbook 06: No se generan eventos

**Síntoma:** hay video y detecciones, pero `vision_core_events_emitted_total`
no crece y el monitor no muestra entradas/salidas.

## Verificación rápida

```bash
curl http://127.0.0.1:8080/ready
curl http://127.0.0.1:8080/metrics
curl http://127.0.0.1:8080/api/v1/state
docker compose --profile camera logs --tail 80 vision-core
```

Comprueba primero que `vision_core_frames_processed_total` crece y que el
monitor muestra recuadros. Si no, vuelve al
[runbook de cámara](02-camara-caida-o-rtsp-inestable.md) o al de
[modelo](03-modelo-no-encontrado-o-error-de-inferencia.md).

## Acción

1. **Modo sin calibrar:** con `VISION_CORE_MONITOR_UNCALIBRATED=1` no se
   inventan zonas ni cruces. Es el valor por defecto del perfil `camera` en
   Compose hasta calibrar.
   Para activar analítica real, configura `VISION_CORE_ZONES_FILE` y pon la
   variable a `0`, después recrea el contenedor.
2. **Archivo de zonas:** debe existir, tener `version: "1.0"` y contener
   `door`, `exterior` e `interior` con polígonos de al menos 3 puntos.
   Ejemplo: [zones.example.json](../../config/zones.example.json). No añadas
   claves desconocidas ni duplicadas: el loader las rechaza.
3. **Resolución:** el `frame_size` del JSON debe coincidir con el frame real.
   Si cambió cámara, encuadre o resolución, captura una referencia y
   recalibra:

   ```bash
   python -m vision_core.scripts.capture_reference referencia.png
   python -m vision_core.scripts.check_zones referencia.png config/zones.json zonas.png
   ```

   El protocolo completo está en
   [validation.md](../validation.md#calibrar-puerta-y-zonas-con-la-cámara).
4. **Confirmación:** por defecto hacen falta 3 observaciones consecutivas en
   origen y destino (`VISION_CORE_ZONE_CONFIRMATION_FRAMES`). Aumentarla reduce
   falsos positivos pero añade retraso; mide antes de cambiarla.
5. **Geometría:** el centro del bbox debe entrar en `exterior` y después en
   `interior` (o la transición inversa). Interior tiene prioridad en
   solapamientos. La región dibujada como "puerta" no restringe por sí sola
   los eventos. `exterior → fuera` produce `FALSE_ALARM`.
6. **Persistencia:** con `VISION_CORE_DB_FAIL_OPEN=1` un fallo de SQLite no
   impide emitir eventos; se siguen publicando en memoria. Consulta
   `persistence` en `/api/v1/state` y el
   [runbook de disco](04-disco-lleno-y-retencion.md) si hay fallos.
7. **Zonas de demo:** `VISION_CORE_MONITOR_DEMO_ZONES=1` solo dibuja zonas de
   demostración en el monitor; no son calibración real.

## Señal de éxito

- `vision_core_events_emitted_total` aumenta al cruzar la zona y
  `/api/v1/state` muestra el evento.
- Si hay base configurada, aparece en `events` con `event_id` único y
  `schema_version=1.0.0`. Consultas en
  [persistence.md](../persistence.md#esquema-y-migraciones).
- El tipo de evento coincide con la acción real (`PERSON_ENTERED`,
  `PERSON_EXITED` o `FALSE_ALARM`).

## Escalado

Si la geometría parece correcta pero no hay eventos, registra una captura de
referencia, el JSON de zonas (sin credenciales) y los contadores, y escala al
responsable de calibración. No reescales polígonos a ciegas. Glosario de
términos en [glossary.md](../glossary.md).
