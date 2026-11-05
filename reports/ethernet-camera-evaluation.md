# Vivotek FD8134 y memoria de reingreso

Validación: 2026-11-04.

## Conexión real

- Webcam sustituida por Vivotek FD8134 conectada a Ethernet `enp3s0`.
- MAC observada: `00:02:d1:1d:d7:bf`. DHCP de NetworkManager: `192.168.50.72`.
- Stream comprobado: `/live.sdp` por RTSP/TCP 554, sin solicitar credenciales.
- Frigate en Docker recibe la cámara; Vision Core consume su restream en 28554.
- Se aplicó una excepción limitada a Frigate→cámara:554 en la cadena de red
  compartida. La conexión desde Docker pasó después de esa excepción.
- 100 frames BGR uint8, H.264, 1280 × 800, sin reconexiones, `status=ok`.
- Apertura: 991 ms; lectura media 24,32 ms y p95 34,86 ms. Los 41,11 frames/s
  consumidos incluyen búfer inicial y no certifican los FPS del sensor. ffprobe
  no informó una tasa válida (`0/0`).
- Monitor: `running`, frames avanzando y una muestra de 29,7 FPS de análisis.
  En esa muestra no había personas detectadas. No se certificó precisión ni
  latencia absoluta de cámara a pantalla.

## Memoria y conteo

180 pruebas pasaron y 4 se omitieron. Nuevas pruebas controladas verifican:

- Regreso antes de que expire el track recupera la misma identidad.
- Memoria de sesión conserva una identidad tras tres horas de ausencia simulada.
- Una vista frontal sigue disponible aunque la última vista fuera de espaldas.
- Personas visibles no comparten identidad; tracks retenidos se reservan antes
  de resolver detecciones nuevas.
- Candidatos ambiguos no se fusionan deliberadamente.
- Entrada, salida y reingreso de una misma identidad: un visitante único;
  ocupación 1→0→1. Una segunda persona aumenta ambos a 2.

La validación de memoria es con embeddings y reloj controlados. Falta medir
recuperación de identidad con personas reales entrando/saliendo en el encuadre
final. El extractor actual usa características ImageNet, no un modelo ReID
entrenado específicamente para personas, por lo que no hay garantía de reconocer
todos los retornos o evitar todos los cambios de identidad.

Se ejecuta `--uncalibrated`: la cámara funciona a su resolución nativa, sin
polígonos ficticios ni eventos de sala. La calibración y el control explícito de
inicio/final de reunión siguen pendientes por decisión del usuario. Al reiniciar
el monitor se borra la memoria temporal y comienza una nueva sesión.
