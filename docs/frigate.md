# Configurar Frigate para Vision Core

Vision Core consume el restream RTSP de Frigate/go2rtc. Las credenciales y la
conexión a la cámara pertenecen a Frigate; no hace falta cambiar el adaptador
Python al pasar de la webcam al servidor de la sala.

## Prueba local con la webcam (Linux)

Incluimos `docker-compose.webcam.yml` como complemento del Compose base. Usa
la webcam mediante V4L2, convierte a H.264 y muestra la cámara `entrada` en Frigate.
La detección de esa cámara, grabación, snapshots y MQTT están desactivados.
La analítica se ejecuta en Vision Core. Configuración basada en la
[guía oficial para webcams](https://docs.frigate.video/configuration/camera_specific/#usb-cameras-aka-webcams)
y [FFmpeg Device de go2rtc](https://github.com/AlexxIT/go2rtc/blob/master/internal/ffmpeg/device/README.md).

1. Identifica el dispositivo y sus formatos:

```bash
ls /dev/video*
ffmpeg -hide_banner -f v4l2 -list_formats all -i /dev/video0
```

El comando de FFmpeg puede terminar con error después de listar los formatos;
no es una prueba de captura. Cierra otras aplicaciones que ocupen la webcam.
El ejemplo usa 640 × 480 a 15 FPS; ajusta `video_size`, `framerate` y las dimensiones
`detect` si tu cámara necesita otro modo.

2. Prepara archivos locales (solo copia si aún no existen):

```bash
cp -n .env.example .env
mkdir -p config/frigate-local
cp -n config/frigate.webcam.example.yml config/frigate-local/config.yml
docker compose -f docker-compose.yml -f docker-compose.webcam.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.webcam.yml up -d frigate
```

En `.env`, `FRIGATE_WEBCAM_DEVICE` selecciona el dispositivo del host (por defecto
`/dev/video0`); dentro del contenedor siempre se mapea a `/dev/video0`.
`config/frigate-local/` contiene configuración editable y base de datos, ignoradas
por Git. No reemplaces su configuración con el ejemplo si ya la modificaste.
La etiqueta Docker `stable` es mutable; la prueba del 2026-11-03 usó Frigate
`0.17.2-3d4dd3a`. Registra la versión si actualizas la imagen.

3. Abre **http://127.0.0.1:15000** y selecciona `entrada` para ver la webcam.
La interfaz local utiliza el puerto interno 5000 sin autenticación; solo se
publica en loopback. RTSP también queda limitado al host. No se necesita abrir
el puerto WebRTC para la visualización MSE de este stream H.264.

4. Desde Python en la laptop:

```bash
# En .env: VISION_CORE_RTSP_URL=rtsp://127.0.0.1:28554/entrada
set -a
source .env
set +a
python -m infrastructure.video.check_stream --frames 100 --transport tcp
# Opcional: comprobar también YOLO con pesos disponibles.
python -m infrastructure.video.check_stream --frames 100 --transport tcp --detector
```

El puerto externo 28554 evita conflictos con otros servicios; Frigate conserva
8554 dentro de Docker. Si cambias el puerto publicado, actualiza también `.env`.
Antes de ejecutar `main.py`, captura referencia y calibra zonas siguiendo
[la guía de validación](validation.md#calibrar-puerta-y-zonas-con-la-cámara).
Para ejecutar Vision Core en Docker después de calibrar:

```bash
docker compose -f docker-compose.yml -f docker-compose.webcam.yml up -d --build vision-core
```

El complemento fija `rtsp://frigate:8554/entrada` para Vision Core dentro de Docker
y espera a que Frigate esté saludable. Esa comprobación no garantiza que haya
frames: verifica siempre con `check_stream`.

Para detener la prueba y liberar la webcam:

```bash
docker compose -f docker-compose.yml -f docker-compose.webcam.yml down
```

Esto conserva `config/frigate-local/`. No se configura reinicio automático.
No se modifican otros contenedores Frigate que ya tengas instalados.

## Ver la analítica de Vision Core

La interfaz de Frigate muestra la cámara. Para ver cajas, IDs y eventos del
pipeline propio, inicia [el monitor de Vision Core](monitor.md) y abre
http://127.0.0.1:8080. No es necesario activar la detección en Frigate.

## Cambiar al Frigate de la sala

1. Detén el Compose local con el comando anterior.
2. Establece en `.env` `VISION_CORE_RTSP_URL=rtsp://HOST_FRIGATE:8554/NOMBRE_STREAM`
   usando el restream existente y sus credenciales, si las requiere.
3. Exporta `.env` de nuevo para Python. En Docker usa solamente
   `docker compose up -d --build vision-core`, sin el complemento de webcam:
   este complemento sobrescribe la URL con el Frigate local.
4. Valida 100 frames, captura una nueva referencia y recalibra las zonas de la sala.

El servidor debe ser accesible desde donde se ejecute Vision Core. No uses
`localhost` para referirte a otro servidor ni al host desde un contenedor.
Solo cambia la configuración de conexión y la calibración; el pipeline es el mismo.

## Configurar el servidor remoto si aún no tiene restream

Instala Frigate siguiendo su [guía oficial](https://docs.frigate.video/frigate/installation/).
Conserva la configuración del servidor y añade el stream; no sustituyas sus cámaras.

En el archivo de configuración de Frigate, integra estos bloques (ejemplo con
valores por reemplazar; `RUTA_REAL` no es una ruta Vivotek conocida):

```yaml
go2rtc:
  streams:
    entrada:
      - "rtsp://USUARIO:CLAVE@IP_CAMARA:554/RUTA_REAL"

cameras:
  entrada:
    ffmpeg:
      inputs:
        - path: rtsp://127.0.0.1:8554/entrada
          input_args: preset-rtsp-restream
          roles:
            - detect
```

Valida el YAML con la versión de Frigate instalada y reinicia ese servicio según
su despliegue. Publica `8554:8554` TCP en el servicio **Frigate** si Vision Core
accede desde fuera de su red Docker. No necesitas publicar ese puerto en Vision
Core: es el cliente. Si comparten una red Docker, puede usarse el nombre DNS del
servicio Frigate. La URL `127.0.0.1` del bloque anterior es interna a Frigate.

Vision Core recibe el restream sin anotaciones en
`rtsp://IP_FRIGATE:8554/entrada`. Esa IP es la del servidor Frigate, no la de la
cámara. El nombre debe coincidir exactamente con `go2rtc.streams`. Consulta la
[documentación oficial del restream](https://docs.frigate.video/configuration/restream/).

Si se activa autenticación RTSP en go2rtc, utiliza sus credenciales en la URL de
Vision Core; pueden ser distintas de las de la cámara o del acceso web a Frigate.
Codifica caracteres reservados del usuario/contraseña como URL. No guardes claves
reales en ejemplos versionados. `.env` está ignorado por Git.

La Vivotek antigua requiere identificar modelo, puerto, credenciales y ruta RTSP.
Que funcione su interfaz en Internet Explorer no confirma esa ruta ni el códec.
No se automatiza la búsqueda ni se supone una ruta universal. Una vez funcionando
Frigate, Vision Core no necesita acceder a esa interfaz web.

Desde la raíz del proyecto con `.env` exportado:

```bash
python -m infrastructure.video.check_stream --frames 100 --transport tcp
python -m infrastructure.video.check_stream --frames 100 --transport tcp --detector
```

El primero inspecciona con ffprobe y lee frames; el segundo añade YOLO. El código
de salida 1 puede significar inspección incompleta aunque la lectura funcione:
revisa el JSON. Después captura referencia y calibra las zonas antes de `main.py`.
