# Runbook 01: Arranque y parada

**Síntoma:** hay que iniciar, reiniciar o detener Vision Core, o no se sabe si
el arranque terminó bien.

## Verificación rápida

```bash
docker compose ps -a
docker compose --profile camera ps -a
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/ready
```

`/health` responde `{"status":"alive","live":true}`. `/ready` debe devolver
`200`; con `503`, abre el runbook del chequeo que falla (video, modelo o disco).

## Acción

### Stack por defecto (video sintético, sin cámara)

```bash
docker compose up            # primer plano; Ctrl+C detiene
docker compose up -d         # segundo plano
docker compose down          # parar y retirar contenedores
```

### Stack con cámara

```bash
docker compose --profile camera up
docker compose --profile camera up -d
docker compose down
```

El perfil `camera` inicia, en orden, `camera-bridge`, `frigate-config`,
`frigate` y `vision-core`. `frigate-config` con `Exited (0)` es correcto: solo
copia la configuración si todavía no existe. Monitor: http://127.0.0.1:8080;
Frigate: http://127.0.0.1:15000.

### Python local

```bash
set -a
source .env
set +a
python main.py
```

Python **no** carga `.env` por sí solo. Para el flujo sintético usa `make setup`
y `make run`.

### Reinicio tras un cambio de código o configuración

```bash
docker compose --profile camera up --build
docker compose --profile camera up -d   # recrea el contenedor si cambió .env
```

Si solo hay que reiniciar un servicio ya construido:
`docker compose --profile camera restart vision-core`.

## Señal de éxito

- `docker compose ps -a` muestra los servicios esperados sin `unhealthy`.
- `/ready` devuelve `200` y `/metrics` muestra
  `vision_core_frames_processed_total` creciendo.
- El monitor muestra recuadros. Si el perfil es `camera`, Frigate responde en
  15000 y el stream en 28554.

## Problemas frecuentes

| Síntoma | Acción |
|---|---|
| Falta `.env` | `cp .env.example .env` y rellenar `FRIGATE_CAMERA_RTSP_URL`. |
| Puerto 8080/15000/28554 ocupado | Detener el monitor Python antiguo o ajustar Compose y `.env` juntos. |
| Puente no saludable | Ir al [runbook de cámara](02-camara-caida-o-rtsp-inestable.md). |
| Modelo pendiente de descarga | El primer arranque necesita Internet; ir al [runbook de modelo](03-modelo-no-encontrado-o-error-de-inferencia.md). |
| `vision-core` se reinicia en bucle | Revisar `docker compose --profile camera logs --tail 80 vision-core`; no borrar la DB antes de copiarla. |

## Escalado

Si `/ready` sigue en `503` tras corregir la causa, registra el `error_code` y
escala con el responsable del servicio. No aumentes timeouts ni desactives
chequeos sin medir antes. Detalle en [startup.md](../startup.md) y
[development.md](../development.md).

## Evidencia ECM-104

Simulacro `container_restart`: detección en 0.50 s y recuperación en 15.00 s,
dentro del objetivo de 15.00 s. `/health` volvió a `alive` y el `uptime` se
reinició con el proceso; los IDs de sesión y el historial volátil no se
conservan. Evidencia completa en
[resultados de simulacros](../../reports/incident-drills.md).
