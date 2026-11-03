# Configurar Frigate para Vision Core

Frigate es un servicio externo. Instálalo en el servidor de cámaras mediante su
[guía oficial de instalación](https://docs.frigate.video/frigate/installation/),
que incluye Docker Compose y requisitos de almacenamiento/hardware. El Compose
 de este repositorio no instala Frigate. Conserva la configuración existente del
servidor y añade el stream; no sustituyas todas sus cámaras por este ejemplo.

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
