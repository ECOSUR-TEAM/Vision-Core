# Vivotek FD8134 por Ethernet

La cámara está conectada directamente a `enp3s0`. Se observó que pide una dirección
por DHCP; no tenía una IP utilizable con la conexión link-local anterior.

Se creó el perfil NetworkManager `vision-core-camera`, con:

- Dirección de la laptop: `192.168.50.1/24`.
- Método IPv4 compartido, que proporciona DHCP a la cámara.
- Sin ruta predeterminada por Ethernet. Internet sigue por Wi-Fi.
- Activación automática deshabilitada; se activa de forma explícita.

```bash
nmcli connection up vision-core-camera
ip neigh show dev enp3s0
```

La MAC `00:02:d1:1d:d7:bf` recibió `192.168.50.72`. Se comprobó directamente
`rtsp://192.168.50.72:554/live.sdp`: video H.264, 1280 × 800. Esta es la dirección
observada, no una IP de fábrica. Si DHCP cambia la dirección, actualiza `.env`.
La interfaz web de esa cámara está en http://192.168.50.72/.

## Frigate

El complemento `docker-compose.camera.yml` sustituye al de webcam. No combina
ambos complementos. La URL de la cámara se conserva en `.env`, ignorado por Git:

```bash
# En .env:
# FRIGATE_CAMERA_RTSP_URL='rtsp://192.168.50.72:554/live.sdp'
# VISION_CORE_RTSP_URL=rtsp://127.0.0.1:28554/entrada
mkdir -p config/frigate-camera-local
cp -n config/frigate.camera.example.yml config/frigate-camera-local/config.yml
docker compose -f docker-compose.yml -f docker-compose.camera.yml up -d frigate
```

La configuración usa la [sustitución de variables de Frigate](https://docs.frigate.video/configuration/advanced/system/).
La carpeta local guarda la base de datos y configuración de este Frigate y no se
versiona. El servicio no requiere acceso a `/dev/video0`.

Frigate: http://127.0.0.1:15000/. Restream para Vision Core:
`rtsp://127.0.0.1:28554/entrada`. La webcam ya no es la fuente de este servicio.

## Acceso desde Docker a Ethernet

En esta laptop, la cadena `nm-sh-fw-enp3s0` rechaza conexiones nuevas hacia
Ethernet antes de las reglas de Docker. El host puede leer la cámara mientras
Frigate devuelve `connection refused` y el restream devuelve 404.

Después de activar el perfil e iniciar Frigate, aplica la excepción con:

```bash
sudo bash scripts/allow_camera_rtsp.sh
# Si cambió la IP: sudo bash scripts/allow_camera_rtsp.sh IP_NUEVA
```

El script detecta la IP y bridge actuales del contenedor y comprueba si la regla
ya existe. Si la cadena no existe, activa primero `vision-core-camera`.

La regla equivalente observada para este despliegue es:

```bash
sudo iptables -I nm-sh-fw-enp3s0 1 \
  -i br-d119385bb2ca -o enp3s0 \
  -s 172.22.0.2/32 -d 192.168.50.72/32 \
  -p tcp --dport 554 \
  -m comment --comment vision-core-camera-rtsp -j ACCEPT
```

Permite únicamente RTSP/TCP desde ese contenedor hacia esa cámara. No desactiva
el firewall. La regla no es persistente: al reiniciar o reactivar el perfil,
comprueba si sigue presente antes de volver a añadirla. Si cambia el contenedor,
bridge o IP de cámara, adapta los valores; no los extrapoles a otro equipo.

Para consultar la dirección y red del contenedor:

```bash
docker inspect vision-core-frigate-1 --format '{{json .NetworkSettings.Networks}}'
sudo iptables -S nm-sh-fw-enp3s0
```

Para retirar exactamente la excepción anterior:

```bash
sudo iptables -D nm-sh-fw-enp3s0 \
  -i br-d119385bb2ca -o enp3s0 \
  -s 172.22.0.2/32 -d 192.168.50.72/32 \
  -p tcp --dport 554 \
  -m comment --comment vision-core-camera-rtsp -j ACCEPT
```

## Monitor y memoria

Mientras no se calibren exterior, interior y puerta, inicia así:

```bash
set -a
source .env
set +a
python -m infrastructure.monitor --uncalibrated --port 8080
```

Admite la resolución nativa, muestra personas y mantiene sus identidades, pero
no inventa cruces ni aforo a partir de zonas de ejemplo. Después de calibrar,
usa `--zones config/zones.json` en lugar de `--uncalibrated`.

La memoria predeterminada dura esta ejecución (`VISION_CORE_REID_TTL_SECONDS=0`).
El control de comienzo y final de una reunión se implementará después. Consulta
[la memoria y el conteo de reingresos](../infrastructure/reid/README.md).

## Detener y volver a la conexión anterior

Detén el monitor con Ctrl+C y Frigate con:

```bash
docker compose -f docker-compose.yml -f docker-compose.camera.yml down
# Solo si deseas devolver Ethernet al perfil anterior:
nmcli connection up netplan-enp3s0
```

No se cambió la configuración permanente de la cámara ni se hizo un reset.


## Resultado comprobado

La Vivotek se leyó a través de Frigate: 100 imágenes de 1280 × 800, sin
reconexiones. El monitor quedó activo en 8080 con memoria de sesión y sin zonas
calibradas. [Informe y límites de la prueba](../reports/ethernet-camera-evaluation.md).
