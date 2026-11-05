# Arranque único con Docker Compose

Desde la raíz del proyecto:

```bash
docker compose up
```

Abre **http://127.0.0.1:8080** para ver Vision Core. Frigate está en
**http://127.0.0.1:15000**. La cámara debe estar encendida y conectada por Ethernet.

En esta laptop, `.env`, el perfil Ethernet y la cámara ya están preparados. No
hace falta activar el entorno Python, ejecutar `main.py`, iniciar el monitor por
separado ni añadir reglas con `iptables`.

Para dejarlo en segundo plano y detenerlo después:

```bash
docker compose up -d
docker compose down
```

`up` en primer plano muestra los logs; Ctrl+C detiene los servicios. `down` los
detiene y retira sus contenedores. La configuración de Frigate y la caché de
modelos se conservan. La memoria de personas es temporal: se vacía al reiniciar
Vision Core, aunque se conserven esos archivos.

## Qué se inicia

1. `camera-bridge`: conecta la cámara desde la red del host y comprueba que responde.
2. `frigate-config`: copia el ejemplo solo si aún no existe una configuración local.
   Terminar con código 0 es normal; este servicio no queda ejecutándose.
3. `frigate`: publica el video cuando el puente está disponible.
4. `vision-core`: inicia el monitor cuando Frigate está saludable.

El puente permite a Frigate alcanzar la cámara conectada directamente a Ethernet
sin modificar el firewall. Solo reenvía TCP al host/puerto de la cámara configurada;
no es un proxy abierto a destinos arbitrarios. Escucha en la dirección interna
del host para Docker, puerto 15554, no en la IP Wi-Fi. Se requiere Docker Engine
sobre Linux con soporte de `host-gateway` y red de host.

Los procesos persistentes usan `restart: unless-stopped`. Si la captura agota sus
reintentos, el monitor termina con error y Docker lo reinicia. Ese reinicio pierde
la memoria temporal de personas. Los checks de salud indican si hay video actual.

## Preparación en otra instalación

Esta sección se realiza una vez; no forma parte del arranque diario.

- Instala Docker Engine y Compose en Linux.
- Copia `.env.example` a `.env` y configura `FRIGATE_CAMERA_RTSP_URL` con la URL real.
- Prepara Ethernet/DHCP si la cámara se conecta directamente; consulta
  [la guía de la FD8134](ethernet-camera.md).
- Ejecuta `docker compose up`. La primera vez construye las imágenes y puede
  descargar dependencias y pesos. Los siguientes arranques reutilizan las imágenes.

`.env` puede contener credenciales y no se incluye en Git ni en la imagen.
El puente conserva usuario, contraseña, ruta y query del RTSP al redirigirlo.
Este montaje usa RTSP/TCP; no reenvía RTP por UDP.

La imagen de Vision Core usa PyTorch para CPU. No se monta el entorno `venv` de
la laptop. La caché de torchvision se conserva en el volumen `vision-model-cache`.
YOLO usa `yolov8n.pt` si existe al construir, o descarga sus pesos al primer uso.

## Cuando calibremos la sala

Guarda los polígonos en `config/zones.json` y cambia en `.env`:

```dotenv
VISION_CORE_MONITOR_UNCALIBRATED=0
VISION_CORE_ZONES_FILE=config/zones.json
```

Vuelve a ejecutar `docker compose up -d`. Compose recrea el monitor con la nueva
configuración. Antes de calibrar se utiliza `VISION_CORE_MONITOR_UNCALIBRATED=1`,
que admite la resolución nativa sin inventar entradas/salidas.

Para actualizar código, reconstruye la imagen:

```bash
docker compose up --build
```

## Diagnóstico

```bash
docker compose ps -a
docker compose logs --tail 80 vision-core
docker compose logs --tail 80 camera-bridge
```

- Puente no saludable: comprueba alimentación, Ethernet y la IP de la cámara.
- Si DHCP cambió la IP, actualiza `FRIGATE_CAMERA_RTSP_URL` en `.env` y ejecuta `up`.
- Puerto 8080 ocupado: detén un monitor Python antiguo antes del primer arranque
  unificado. Después de migrar, todo el monitor se controla con Compose.
- `frigate-config` con estado `Exited (0)` es correcto.
- Modelos pendientes de descarga: el primer arranque necesita Internet; los pesos
  ya descargados se reutilizan.

Los archivos `docker-compose.camera.yml` y `docker-compose.monitor.yml` son alias
vacíos de compatibilidad; ya no se necesitan. La webcam es una alternativa de
desarrollo independiente con `docker-compose.webcam.yml`, no un complemento al
arranque principal. Detén el conjunto principal antes de usarla.
