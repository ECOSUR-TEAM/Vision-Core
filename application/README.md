# Orquestación del pipeline

`VisionCoreApp` recibe por constructor las implementaciones de `VideoSource`,
`DetectorManager`, `ReIDMemory` y `DoorAnalytics`, más los callables del extractor
y la salida de eventos. Solo importa contratos y entidades del dominio;
`main.py` construye e inyecta los adaptadores de infraestructura. No se cargan
modelos ni conexiones al crear/importar la aplicación por sí sola.

Cada iteración:

1. Lee un frame BGR. `None` termina la fuente; un fallo de conexión es una excepción.
2. Ejecuta detección y tracking mediante `DetectorManager.process(frame)`.
3. Consume `pop_lost_track_ids()`, entrega el último embedding a `mark_lost` y
   elimina los mappings expirados antes de resolver nuevas detecciones.
4. Recorta cada persona, extrae su embedding y resuelve `track_id → person_id`.
5. Entrega el `person_id` y el centro del bounding box a `DoorAnalytics.update`,
   conforme a su contrato. Emite únicamente eventos distintos de `None`.

Los recortes se limitan al frame usando floor/ceil para conservar cajas
fraccionarias pequeñas. Cajas sin área, no finitas o totalmente fuera del frame
producen un error explícito antes de invocar el extractor.

La recuperación de RTSP corresponde al adaptador de video. Si agota sus intentos,
o cualquier etapa falla, la aplicación intenta cerrar la fuente y propaga el
error. También cierra en EOF y ante `KeyboardInterrupt`. Si el cierre falla durante
otro error, registra el tipo del fallo de cierre y conserva el error original.
Si falla únicamente el cierre, propaga ese fallo. No descarta silenciosamente
frames ni errores del detector, ReID, analítica o consumidor de eventos.

`main.py` conecta RTSP, YOLO con tracking, InMemoryReID, el extractor torchvision,
PolygonDoorAnalytics y salida JSON. Los polígonos actuales son ejemplos: deben
ajustarse a la imagen de la sala antes de validar eventos reales.

Pruebas: `python -m pytest tests/application -q`. Incluyen recorrido con fuente y
detecciones simuladas, ReID y zonas reales, reaparición con identidad persistente,
recortes fraccionarios, independencia de infraestructura y errores en cada etapa.
No sustituyen una prueba con Frigate y la cámara física.
