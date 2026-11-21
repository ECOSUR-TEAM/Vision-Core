# Exposición del monitor y binding

## Binding por defecto

La ejecución local usa `127.0.0.1` por defecto: `Settings.from_env` toma ese
valor cuando `VISION_CORE_MONITOR_HOST` no está definido y `main.py` usa el
valor de settings como valor por defecto de `--host`.

```bash
python main.py --demo-zones
# Vision Core: http://127.0.0.1:8080
```

## Exposición explícita

`0.0.0.0` solo se usa de forma explícita:

```bash
VISION_CORE_MONITOR_HOST=0.0.0.0 python main.py --demo-zones
# o: python main.py --demo-zones --host 0.0.0.0
```

Al detectar `--host 0.0.0.0`, el monitor imprime una advertencia en stdout:
expone el servicio sin autenticación y requiere los controles del ticket 42.

Dentro de Docker el contenedor necesita escuchar en `0.0.0.0` para que el
puerto publicado funcione; por eso el `Dockerfile` y los archivos Compose lo
fijan de forma explícita. El control de exposición real es la publicación del
puerto, que en todos los Compose está atada a `127.0.0.1`.

## Riesgo

El monitor sirve video y eventos de personas. Publicarlo en `0.0.0.0` sin
autenticación revela imágenes y eventos a cualquier cliente que pueda alcanzar
el puerto, incluidos otros contenedores de la misma red. No se asume que Docker
aisla suficiente.

Antes de publicar en LAN o Internet debe implementarse el ticket 42
(autenticación, RBAC, TLS y privacidad). Los tickets 46 (límites HTTP) y 47
(headers de seguridad) son complementarios y no sustituyen esa dependencia.

## Cómo verificar puertos y binding

En local:

```bash
python main.py --demo-zones
ss -ltnp | grep 8080     # debe mostrar 127.0.0.1:8080
```

En Docker:

```bash
docker compose ps
docker compose port vision-core 8080   # debe devolver 127.0.0.1:<puerto>
```

Revisión automática:

```bash
python -m pytest tests/infrastructure/monitor/test_monitor_binding.py -q
```
