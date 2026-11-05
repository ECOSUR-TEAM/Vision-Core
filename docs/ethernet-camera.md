# Vivotek FD8134 por Ethernet

## Uso diario

```bash
docker compose up
```

Monitor: http://127.0.0.1:8080/. Frigate: http://127.0.0.1:15000/.
Para detener: `docker compose down`. [Guía de arranque único](startup.md).

## Red preparada en esta laptop

La cámara pide una IP por DHCP. Se creó el perfil NetworkManager
`vision-core-camera` para `enp3s0`, con dirección `192.168.50.1/24`, método IPv4
compartido y sin ruta predeterminada por Ethernet. Wi-Fi sigue dando Internet.
La activación automática está habilitada con prioridad 100: al conectar el cable
se prefiere este perfil sobre el perfil link-local anterior.

La MAC `00:02:d1:1d:d7:bf` recibió `192.168.50.72`. Se comprobó
`rtsp://192.168.50.72:554/live.sdp`: H.264, 1280 × 800. Es la dirección observada,
no una IP de fábrica. Si cambia, actualiza `FRIGATE_CAMERA_RTSP_URL` en `.env`.
La interfaz web de la cámara es http://192.168.50.72/.

Para preparar otro equipo Linux una sola vez, ajustando interfaz/subred:

```bash
nmcli connection add type ethernet ifname enp3s0 con-name vision-core-camera \
  ipv4.method shared ipv4.addresses 192.168.50.1/24 ipv4.never-default yes \
  ipv6.method disabled connection.autoconnect yes connection.autoconnect-priority 100
nmcli connection up vision-core-camera
```

No vuelvas a crear el perfil si ya existe. No se cambió la configuración permanente
de la cámara ni se hizo un reset. El arranque diario no requiere comandos `nmcli`.

## Docker y la red compartida

NetworkManager rechaza conexiones nuevas desde redes externas hacia Ethernet.
El arranque antiguo necesitaba una excepción de firewall para Frigate. El Compose
actual utiliza `camera-bridge`, que establece la conexión a la cámara desde el
host y entrega el TCP a Frigate. No requiere permisos de administrador del host,
contenedores privilegiados, acceso al socket Docker ni modificar el firewall.

El puente preserva la URL original en `.env`. El punto de entrada de Frigate
reescribe su destino al puente, conservando ruta y credenciales. Los archivos
locales de Frigate se mantienen en `config/frigate-camera-local/`, fuera de Git.
La configuración inicial se prepara automáticamente sin sobrescribirla.

`scripts/allow_camera_rtsp.sh` queda únicamente para el montaje anterior; no se
usa en el arranque actual. Una excepción antigua no es necesaria para este flujo.

## Monitor y memoria

El arranque principal usa detección sin calibración por defecto y acepta la
resolución nativa de la FD8134. No genera cruces de sala hasta que existan zonas
reales. Después de calibrar, cambia `VISION_CORE_MONITOR_UNCALIBRATED=0` en `.env`.

La memoria dura esta ejecución (`VISION_CORE_REID_TTL_SECONDS=0`). El control de
reuniones queda pendiente. [Memoria y reingresos](../infrastructure/reid/README.md).

## Volver al perfil Ethernet anterior

Solo si ya no vas a usar la conexión directa con la cámara:

```bash
docker compose down
nmcli connection modify vision-core-camera connection.autoconnect no
nmcli connection up netplan-enp3s0
```

[Informe previo de conexión y límites](../reports/ethernet-camera-evaluation.md).
