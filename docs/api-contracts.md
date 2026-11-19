# Contratos versionados: API del monitor y eventos

Este documento fija los contratos públicos de los límites del sistema. Las
implementaciones pueden cambiar sin aviso siempre que estos contratos no se
rompan. Los errores se detallan en el [catálogo](errors.md).

## API HTTP del monitor

Versión actual: `v1`. Prefijo: `/api/v1/`. El panel en `/` no está versionado.

| Ruta | Éxito | Errores |
|---|---|---|
| `GET /api/v1/state` | 200, JSON con estado, personas, métricas y eventos. | Envelope JSON; 500 si falla el caso de uso. |
| `GET /api/v1/frame` | 200, JPEG anotado. | 503 `VIDEO_FRAME_PENDING` si aún no hay imagen. |
| `GET /api/v1/frame?after=N` | 200 con imagen nueva, 204 sin imagen nueva tras 1 s. | 400 `VALIDATION_FAILED` si `N` no es entero no negativo. |
| Cualquier otra ruta | — | 404 `REQUEST_NOT_FOUND`. |

`N` debe ser un entero `>= 0`. Las respuestas exitosas de frame incluyen
`X-Frame-Sequence`. Todas las respuestas incluyen:

- `Content-Type` (`application/json`, `image/jpeg` o `text/html; charset=utf-8`).
- `Content-Length` y `Cache-Control: no-store`.
- `X-Content-Type-Options: nosniff`.
- `X-Request-ID`: identificador de una sola petición, también presente en el
  envelope de error; permite correlacionar con logs estructurados.

El cuerpo de `/api/v1/state` contiene: `status`, `error`, `demo_zones`, `frame`,
`updated_at`, `age_seconds`, `people`, `events`, `counts`, `processing_ms`,
`fps`, `dropped_frames`. Cada elemento de `events` sigue el esquema descrito
más abajo.

### Envelope de error

Todo error HTTP del monitor usa exactamente esta forma:

```json
{
  "error": {
    "code": "VIDEO_SOURCE_UNAVAILABLE",
    "message": "No se pudo acceder a la fuente de video.",
    "request_id": "9f0c... "
  }
}
```

`code` y `message` son estables y seguros; `request_id` coincide con la cabecera
`X-Request-ID`. No se exponen stack traces, rutas internas, URLs con
credenciales ni datos personales. Los estados usados son 400, 404, 409, 422,
500 y 503; la tabla de códigos a estados está en
`src/vision_core/features/monitor/infrastructure/http/error_response.py`.

### Rutas obsoletas

`/api/state` y `/api/frame` siguen funcionando como alias de `v1` y responden
con la cabecera `Deprecation: true`. Son un puente temporal: dejarán de
existir en `v2`. El panel y el healthcheck usan ya las rutas versionadas.

## Esquema de eventos

Versión actual: `1.0.0` (`EVENT_SCHEMA_VERSION`). Todo evento serializado
incluye `schema_version`:

```json
{
  "event": "PERSON_ENTERED",
  "person_id": "abc",
  "timestamp": 12.5,
  "metadata": {"from_zone": "exterior", "to_zone": "interior"},
  "schema_version": "1.0.0"
}
```

`event` es uno de `PERSON_ENTERED`, `PERSON_EXITED`, `FALSE_ALARM`.
`person_id` es un identificador de sesión, no una identidad nominal.
`timestamp` es `float` (segundos Unix) y `metadata` es un objeto con valores
serializables. Los productores son los mappers de door y pipeline y el
serializador por defecto de `MonitorState`; todos usan la misma función
`with_schema_version`.

## Política de versionado y deprecación

- API: el número de versión va en la ruta (`/api/v1/`). Añadir un campo opcional
  o una ruta nueva es compatible dentro de `v1`. Cambiar un nombre, quitar un
  campo, cambiar un tipo o alterar el significado de un código exige `v2`.
- Eventos: versión semántica. Cambios compatibles (campo opcional nuevo) elevan
  la parte menor; cambios incompatibles elevan la parte mayor.
- Un cambio incompatible se anuncia en esta documentación antes de aplicarse;
  la versión anterior permanece al menos una versión menor completa. Las rutas
  antiguas se marcan con `Deprecation` desde el primer anuncio.
- Los códigos de error nunca se renombran ni se reutilizan con otro significado.
- Dentro de cada feature, los DTOs son `dataclass(frozen=True, slots=True)`,
  uno por operación y dirección. Solo exponen tipos de `stdlib` y `typing`:
  no aparecen `numpy`, `cv2`, `torch`, ultralytics, entidades de dominio ni
  adaptadores. Los mappers convierten entre DTO y dominio; las pruebas de
  contrato verifican este límite.

Fuera de alcance: generación automática de clientes desde OpenAPI y gRPC.
