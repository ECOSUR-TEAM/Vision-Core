# Editor de zonas del monitor

El monitor puede editar el JSON de zonas desde el navegador y guardarlo en el
mismo archivo que consume el pipeline (`--zones` / `VISION_CORE_ZONES_FILE`).
Está desactivado por defecto: sin marca, las rutas del editor responden
`404 REQUEST_NOT_FOUND` y el panel no muestra el editor.

## Activación

No se usa `--demo-zones` ni `--uncalibrated`: el editor necesita un archivo real.

```bash
set -a
source .env
set +a
export VISION_CORE_ZONE_EDITOR_ENABLED=1
export VISION_CORE_ZONE_EDITOR_TOKEN='cambia-este-token'
export VISION_CORE_ZONE_EDITOR_AUDIT_FILE=/app/data/zone-editor-audit.jsonl
python main.py --zones config/zones.json --zone-editor --port 8080
```

El editor se activa con `VISION_CORE_ZONE_EDITOR_ENABLED=1` o con `--zone-editor`
(no hace falta ambos). En cualquier caso exigen `VISION_CORE_ZONE_EDITOR_TOKEN`
y `VISION_CORE_ZONE_EDITOR_AUDIT_FILE`, y necesitan un archivo real de zonas. El
token se introduce en el panel en cada sesión: no se guarda en el navegador ni
en el archivo de zonas.

## Uso en el panel

El editor aparece al lado del video cuando `GET /api/v1/zones` responde correctamente:

1. Elegir la zona (`Exterior`, `Interior` o `Puerta`).
2. Arrastrar vértices o activar «Añadir vértice» y hacer clic en el canvas.
3. Revisar el aviso de validación; los errores impiden guardar.
4. «Descartar cambios» vuelve al documento cargado.
5. Escribir token y usuario, y pulsar «Guardar zonas».

El canvas dibuja el último frame del monitor como fondo y superpone los tres
polígonos. Los nombres y mensajes se insertan como texto (`textContent`), nunca
como HTML.

## Contrato HTTP

Con la marca activa se añaden estas rutas. Los alias sin versionar están
obsoletos y devuelven `Deprecation: true`.

| Método | Ruta | Cuerpo | Respuesta |
|---|---|---|---|
| `GET` | `/api/v1/zones` | — | `200 {"zones": {...}, "editor": {...}}` |
| `PUT` | `/api/v1/zones` | documento de zonas | `200 {"zones": {...}, "audit": {...}, "restart_required": true}` |
| `POST` | `/api/v1/zones/validate` | documento de zonas | `200 {"zones": {...}}` (no escribe) |

Cabeceras para `PUT`:

- `Content-Type: application/json` (obligatoria).
- `Authorization: Bearer <VISION_CORE_ZONE_EDITOR_TOKEN>` (insensible a mayúsculas).
- `X-Vision-User: <usuario>` (insensible a mayúsculas): sólo se usa para la
  auditoría; no concede permisos.

Errores principales: `403 ZONE_EDITOR_FORBIDDEN` (token ausente o incorrecto),
`404 REQUEST_NOT_FOUND` (editor desactivado), `413 VALIDATION_FAILED` (payload
mayor que 100 KiB), `422 ZONE_CONFIG_INVALID` / `ZONE_GEOMETRY_INVALID`
(esquema o geometría), `400 VALIDATION_FAILED` (JSON, query o tipo de contenido).
Los bytes duplicados de `Content-Length`, las claves JSON repetidas y los
parámetros de consulta se rechazan.

## Validación y escritura

La validación del esquema `1.0` vive en
`src/vision_core/core/validation/zone_payload.py` y la comparten el loader, la
API y los tests. El cliente replica las comprobaciones para avisar antes, pero el
servidor vuelve a validar siempre antes de escribir.

Reglas: `frame_size` son dos enteros positivos; `door`, `exterior` e `interior`
son 3–100 vértices `[x, y]` finitos dentro del frame, sin repeticiones, con área
y sin autointersecciones; no se admiten claves adicionales.

El guardado es atómico: se escribe un temporal en el mismo directorio, se
sustituye el archivo y se conserva una copia de seguridad hasta confirmar. Si
falla la escritura o la auditoría, se restaura el contenido anterior. Cada
cambio correcto añade una línea JSON con `user`, `timestamp` (UTC),
`previous_sha256` y `new_sha256` a `VISION_CORE_ZONE_EDITOR_AUDIT_FILE`, que es
obligatorio al habilitar el editor. Los intentos denegados se registran como
`zone_editor_access_denied` sin incluir el token.

El guardado no recarga la analítica ni el render ya construidos: la respuesta
incluye `restart_required: true` y el panel indica que hay que reiniciar el
monitor para que los nuevos polígonos afecten a la detección de puerta.

## Limitaciones de seguridad

El token es un secreto compartido de una sola capa, no autenticación de
usuarios; `X-Vision-User` es una etiqueta libre y se sanea antes de registrarla.
El monitor sigue sin TLS, RBAC ni sesiones: la autenticación, autorización y
registro de accesos del ticket 42 siguen pendientes. No expongas este editor a
una red no confiable; el bind debe permanecer en loopback o detrás de un proxy
con controles de acceso. Las respuestas mantienen CSP con nonce por petición y
el frontend no usa sinks de HTML dinámico.
