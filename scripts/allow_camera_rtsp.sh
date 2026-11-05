#!/usr/bin/env bash
# Run after activating vision-core-camera and starting Frigate.
# Allows only this project's Frigate container -> specified camera RTSP/TCP.
set -euo pipefail
if (( EUID != 0 )); then
  echo 'Ejecuta: sudo bash scripts/allow_camera_rtsp.sh [IP_CAMARA]' >&2
  exit 1
fi
camera_ip=${1:-192.168.50.72}
if [[ ! $camera_ip =~ ^192\.168\.50\.[0-9]{1,3}$ ]]; then
  echo 'La cámara debe estar en la subred Ethernet 192.168.50.0/24.' >&2
  exit 1
fi
if ! iptables -S nm-sh-fw-enp3s0 >/dev/null 2>&1; then
  echo 'Primero activa Ethernet: nmcli connection up vision-core-camera' >&2
  exit 1
fi
container_ip=$(docker inspect vision-core-frigate-1 --format '{{with index .NetworkSettings.Networks "vision-core_default"}}{{.IPAddress}}{{end}}')
network_id=$(docker network inspect vision-core_default --format '{{.Id}}')
if [[ -z $container_ip || -z $network_id ]]; then
  echo 'Primero inicia Frigate con docker-compose.camera.yml.' >&2
  exit 1
fi
bridge="br-${network_id:0:12}"
rule=(-i "$bridge" -o enp3s0 -s "$container_ip/32" -d "$camera_ip/32"
      -p tcp --dport 554 -m comment --comment vision-core-camera-rtsp -j ACCEPT)
if ! iptables -C nm-sh-fw-enp3s0 "${rule[@]}" 2>/dev/null; then
  iptables -I nm-sh-fw-enp3s0 1 "${rule[@]}"
fi
echo "Acceso RTSP habilitado: Frigate $container_ip -> cámara $camera_ip:554."
